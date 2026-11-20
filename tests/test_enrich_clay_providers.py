"""Clay-standard waterfall providers: Hunter, Apollo, Findymail, People Data Labs.

Each Clay waterfall should port provider-for-provider: same provider order,
same response parsing, cost ledger entries. HTTP is mocked — no real keys.
"""
import urllib.request

import pytest

from gtmharness.adapters import enrich


def _mock_http(monkeypatch, capture, response):
    """Replace _http_json_ex; capture (url, headers, payload, method) per call."""

    def fake(url, headers, payload, method="POST"):
        capture.append({"url": url, "headers": headers, "payload": payload, "method": method})
        return response

    monkeypatch.setattr(enrich, "_http_json_ex", fake)


LEAD = {"first_name": "Jane", "last_name": "Doe", "domain": "acme.ai", "company": "Acme AI"}
CFG = {"HUNTER_API_KEY": "h", "APOLLO_API_KEY": "a", "FINDYMAIL_API_KEY": "f",
       "PEOPLE_DATA_LABS_API_KEY": "pdl"}


def test_hunter_get_with_query_key(monkeypatch):
    cap = []
    _mock_http(monkeypatch, cap, {"data": {"email": "jane@acme.ai"}})
    out = enrich._lookup_hunter(LEAD, CFG)
    req = cap[0]
    assert req["method"] == "GET"
    assert "api.hunter.io/v2/email-finder" in req["url"]
    assert "domain=acme.ai" in req["url"] and "first_name=Jane" in req["url"]
    assert "api_key=h" in req["url"]
    assert out == {"email": "jane@acme.ai", "cost": 0.02}


def test_apollo_header_key_and_person_email(monkeypatch):
    cap = []
    _mock_http(monkeypatch, cap, {"person": {"email": "jane@acme.ai"}})
    out = enrich._lookup_apollo(LEAD, CFG)
    req = cap[0]
    assert req["method"] == "POST"
    assert req["headers"]["X-Api-Key"] == "a"
    assert "X-Api-Key" not in (req["payload"] or {})  # key never in body
    assert req["url"].endswith("/people/match")
    assert out == {"email": "jane@acme.ai", "cost": 0.02}


def test_findymail_bearer_and_email_field(monkeypatch):
    cap = []
    _mock_http(monkeypatch, cap, {"email": "jane@acme.ai", "status": "verified"})
    out = enrich._lookup_findymail(LEAD, CFG)
    req = cap[0]
    assert req["headers"]["Authorization"] == "Bearer f"
    assert req["payload"]["company_name"] == "Acme AI"
    assert out == {"email": "jane@acme.ai", "cost": 0.02}


def test_peopledatalabs_work_email_preferred(monkeypatch):
    cap = []
    _mock_http(monkeypatch, cap, {"data": {"work_email": "jane@acme.ai", "email": "jd@gmail.com"}})
    out = enrich._lookup_peopledatalabs(LEAD, CFG)
    req = cap[0]
    assert req["headers"]["X-API-Key"] == "pdl"
    assert out == {"email": "jane@acme.ai", "cost": 0.05}


def test_missing_keys_raise_runtime_error():
    for name in ("hunter", "apollo", "findymail", "peopledatalabs"):
        with pytest.raises(RuntimeError):
            enrich.PROVIDERS[name]["lookup"](LEAD, {})


def test_clay_waterfall_order_ports_provider_for_provider(monkeypatch):
    """Clay default order: findymail -> hunter -> apollo -> peopledatalabs.
    A miss in the first two must fall through; a hit stops the waterfall."""
    cap = []

    def fake(url, headers, payload, method="POST"):
        cap.append(url)
        if "findymail" in url:
            return {}
        if "hunter.io" in url:
            return {"data": {}}
        return {"person": {"email": "jane@acme.ai"}}

    monkeypatch.setattr(enrich, "_http_json_ex", fake)
    r = enrich.run_waterfall(LEAD, ["findymail", "hunter", "apollo", "peopledatalabs"], CFG)
    assert r.ok and r.provider == "apollo"
    assert len(cap) == 3  # waterfall stopped at the hit
    assert cap[0].startswith("https://app.findymail.com")
    assert cap[1].startswith("https://api.hunter.io")


def test_registry_registered_costs():
    for name, cost in (("hunter", 0.02), ("apollo", 0.02), ("findymail", 0.02),
                       ("peopledatalabs", 0.05)):
        assert enrich.PROVIDERS[name]["cost"] == cost


def test_retry_backoff_on_transient_error(monkeypatch):
    calls = []
    sleeps = []

    class Resp:
        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout):
        calls.append(req.full_url)
        if len(calls) < 3:
            raise OSError("transient")
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(enrich.time, "sleep", lambda s: sleeps.append(s))
    enrich._http_json_ex("https://api.apollo.io/api/v1/people/match", {"X-Api-Key": "a"}, {})
    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]  # exponential backoff
