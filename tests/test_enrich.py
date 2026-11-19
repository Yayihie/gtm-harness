import pytest

from gtmharness import ledger
from gtmharness.adapters import enrich


def test_null_provider_misses_free():
    r = enrich.run_waterfall({"name": "jane", "company": "acme"}, ["null"], {})
    assert not r.ok
    assert r.cost_usd == 0.0
    assert r.attempts == [{"provider": "null", "status": "miss"}]


def test_waterfall_cost_order_and_stop_on_hit(tmp_path):
    # fake cheap provider that hits, expensive one never called
    enrich.PROVIDERS["cheap"] = {"cost": 0.001, "lookup": lambda lead, cfg: {"email": "j@acme.com", "cost": 0.001}}
    enrich.PROVIDERS["expensive"] = {"cost": 0.05, "lookup": lambda lead, cfg: {"email": "x@y.com", "cost": 0.05}}
    r = enrich.run_waterfall({"name": "jane"}, ["cheap", "expensive"], {}, state_dir=tmp_path)
    assert r.ok
    assert r.provider == "cheap"
    assert r.cost_usd == 0.001
    assert [a["status"] for a in r.attempts] == ["hit"]
    # expensive never called
    assert r.attempts[0]["provider"] == "cheap"
    del enrich.PROVIDERS["cheap"], enrich.PROVIDERS["expensive"]


def test_waterfall_falls_through_on_miss(tmp_path):
    enrich.PROVIDERS["miss1"] = {"cost": 0.001, "lookup": lambda lead, cfg: {"email": None, "cost": 0.001}}
    enrich.PROVIDERS["hit2"] = {"cost": 0.002, "lookup": lambda lead, cfg: {"email": "j@acme.com", "cost": 0.002}}
    r = enrich.run_waterfall({"name": "jane"}, ["miss1", "hit2"], {}, state_dir=tmp_path)
    assert r.ok and r.provider == "hit2"
    assert r.cost_usd == 0.003  # both providers charged
    assert [a["status"] for a in r.attempts] == ["miss", "hit"]
    del enrich.PROVIDERS["miss1"], enrich.PROVIDERS["hit2"]


def test_waterfall_unknown_provider_skipped():
    r = enrich.run_waterfall({}, ["nope"], {})
    assert not r.ok
    assert r.attempts[0]["status"] == "unknown provider"


def test_prospeo_requires_key():
    with pytest.raises(RuntimeError, match="PROSPEO_API_KEY"):
        enrich._lookup_prospeo({"name": "jane"}, {})


def test_enrich_rows_logs_ledger(tmp_path):
    enrich.PROVIDERS["free_hit"] = {"cost": 0.0, "lookup": lambda lead, cfg: {"email": "a@b.com", "cost": 0.0}}
    rows = enrich.enrich_rows([{"name": "jane"}], ["free_hit"], {}, state_dir=tmp_path, pipeline="p")
    assert rows[0]["email"] == "a@b.com"
    assert rows[0]["enrich_provider"] == "free_hit"
    totals = ledger.summarize(tmp_path)
    assert "free_hit" in totals
    del enrich.PROVIDERS["free_hit"]
