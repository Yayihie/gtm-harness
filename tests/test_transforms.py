"""Tests for transform execution in `run` (enrich waterfall), budget cap, and lead cache."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from gtmharness.adapters import enrich
from gtmharness.adapters.enrich import BudgetExceeded
from gtmharness.ledger import summarize

# The CLI runs as a subprocess, so provider registration must happen there too.
# sitecustomize.py on PYTHONPATH registers the fake provider at interpreter start.
SITECUSTOMIZE = """import gtmharness.adapters.enrich as enrich
enrich.PROVIDERS["free_hit"] = {
    "cost": 0.01,
    "lookup": lambda lead, cfg: {"email": "found@x.com", "cost": 0.01},
}
"""

PIPE = """
name: enrich_pipeline
steps:
  - name: leads
    kind: source
    using: json
    config: {path: leads.json}
  - name: enrich
    kind: transform
    using: enrich
    config:
      providers: [free_hit]
      provider_config: {}
  - name: out
    kind: sink
    using: dry
    contract:
      - {name: email, type: string, required: true}
"""


@pytest.fixture(autouse=True)
def fake_provider():
    enrich.PROVIDERS["free_hit"] = {"cost": 0.01, "lookup": lambda lead, cfg: {"email": "found@x.com", "cost": 0.01}}
    yield
    del enrich.PROVIDERS["free_hit"]


def setup(tmp_path, leads=None):
    (tmp_path / "pipe.yaml").write_text(PIPE)
    (tmp_path / "leads.json").write_text(json.dumps(leads or [
        {"name": "jane", "company": "acme"},
        {"name": "sam", "company": "contoso"},
    ]))
    (tmp_path / "sitecustomize.py").write_text(SITECUSTOMIZE)


def run_cli(tmp_path, *args):
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    return subprocess.run(
        [sys.executable, "-m", "gtmharness.cli", "--state-dir", str(tmp_path / ".state"), *args],
        capture_output=True, text=True, cwd=str(tmp_path), env=env,
    )


def test_run_executes_enrich_transform(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "run", "pipe.yaml")
    assert r.returncode == 0, r.stdout
    assert "found@x.com" in r.stdout


def test_run_budget_exceeded_aborts(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "run", "pipe.yaml", "--budget", "0.015")
    assert r.returncode == 1
    assert "TRANSFORM ERROR" in r.stdout
    assert "budget exceeded" in r.stdout
    assert "ledger so far" in r.stdout
    assert "RUN ABORTED" in r.stdout


def test_run_budget_high_enough_passes(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "run", "pipe.yaml", "--budget", "1.00")
    assert r.returncode == 0, r.stdout


def test_run_budget_from_step_config(tmp_path):
    setup(tmp_path)
    (tmp_path / "pipe.yaml").write_text(PIPE.replace("providers: [free_hit]",
                                                     "providers: [free_hit]\n      budget_usd: 0.015"))
    r = run_cli(tmp_path, "run", "pipe.yaml")
    assert r.returncode == 1
    assert "budget exceeded" in r.stdout


def test_run_contract_violation_blocks_after_transform(tmp_path):
    # provider returns an email but contract requires lead_source enum too
    setup(tmp_path)
    (tmp_path / "pipe.yaml").write_text(PIPE.replace(
        "- {name: email, type: string, required: true}",
        "- {name: email, type: string, required: true}\n      - {name: lead_source, type: string, enum: [paid]}"))
    r = run_cli(tmp_path, "run", "pipe.yaml")
    assert r.returncode == 1
    assert "contract violations" in r.stdout


def test_enrich_rows_respects_budget_directly(tmp_path):
    rows = [{"name": f"p{i}", "company": "c"} for i in range(5)]
    with pytest.raises(BudgetExceeded):
        enrich.enrich_rows(rows, ["free_hit"], {}, state_dir=tmp_path, budget_usd=0.025)


def test_lead_cache_never_rebuys(tmp_path):
    calls = []
    def lookup(lead, cfg):
        calls.append(lead)
        return {"email": "x@y.com", "cost": 0.01}
    enrich.PROVIDERS["cached"] = {"cost": 0.01, "lookup": lookup}
    lead = {"name": "jane", "company": "acme"}
    r1 = enrich.run_waterfall(lead, ["cached"], {}, state_dir=tmp_path)
    r2 = enrich.run_waterfall(dict(lead), ["cached"], {}, state_dir=tmp_path)
    assert len(calls) == 1  # second call served from cache
    assert r2.attempts[0]["status"] == "cached"
    assert r2.cost_usd == 0.0
    del enrich.PROVIDERS["cached"]


def test_cache_key_variants(tmp_path):
    enrich.PROVIDERS["cached"] = {"cost": 0.01, "lookup": lambda l, c: {"email": "x@y.com", "cost": 0.01}}
    # same email = same cache key even with different name/company
    enrich.run_waterfall({"email": "a@b.com", "name": "jane", "company": "acme"}, ["cached"], {}, state_dir=tmp_path)
    r = enrich.run_waterfall({"email": "a@b.com", "name": "other", "company": "other"}, ["cached"], {}, state_dir=tmp_path)
    assert r.attempts[0]["status"] == "cached"
    del enrich.PROVIDERS["cached"]


def test_ledger_records_provider_calls(tmp_path):
    setup(tmp_path)
    run_cli(tmp_path, "run", "pipe.yaml")
    totals = summarize(tmp_path / ".state")
    assert "free_hit" in totals
    assert totals["free_hit"]["calls"] == 2  # two leads, one paid call each
