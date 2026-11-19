"""Enrichment waterfall adapter — BYO provider keys, cost-ordered, MIT clean-room.

Following the pattern validated by openenrich (AGPL — no code reused):

1. Order providers by cost (cheapest first).
2. Call provider 1; if it returns a verified email, done.
3. Otherwise fall through to the next provider, skipping any lead a provider
   already answered (never buy the same person twice).
4. Every call is logged to the cost ledger with its real price.

Built-in provider registry (BYO keys; each adapter module defines `lookup(lead, config)`):

    name        cost/hit   key config
    prospeo     $0.01      PROSPEO_API_KEY
    leadmagic   $0.02      LEADMAGIC_API_KEY
    null        $0.00      free dry-run provider that always misses

The registry is a dict of provider name -> {"cost": float, "lookup": fn}.
Users add providers by registering in PROVIDERS (or a future plugin entry point).
"""

from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .. import ledger

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_S = 1.0


def _http_json(url: str, api_key: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": api_key},
        method="POST",
    )
    last_err = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except Exception as e:  # transient network/API errors: retry with backoff
            last_err = e
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF_S * (2 ** attempt))
    raise last_err


@dataclass
class WaterfallResult:
    email: str | None = None
    provider: str | None = None
    cost_usd: float = 0.0
    attempts: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.email is not None


# ---------------------------------------------------------------- providers

def _lookup_prospeo(lead: dict, config: dict) -> dict:
    """{email, cost} — real call on your key."""
    key = config.get("PROSPEO_API_KEY")
    if not key:
        raise RuntimeError("prospeo: set PROSPEO_API_KEY in provider config")
    data = _http_json(
        "https://api.prospeo.io/api/email-finder",
        key,
        {"name": lead.get("name", ""), "company": lead.get("company", "")},
    )
    return {"email": data.get("email"), "cost": 0.01}


def _lookup_leadmagic(lead: dict, config: dict) -> dict:
    key = config.get("LEADMAGIC_API_KEY")
    if not key:
        raise RuntimeError("leadmagic: set LEADMAGIC_API_KEY in provider config")
    data = _http_json(
        "https://api.leadmagic.io/email-finder",
        key,
        {"first_name": lead.get("first_name", ""), "last_name": lead.get("last_name", ""),
         "domain": lead.get("domain", "")},
    )
    return {"email": data.get("email"), "cost": 0.02}


def _lookup_null(lead: dict, config: dict) -> dict:
    """Free dry-run provider: always misses, never costs anything."""
    return {"email": None, "cost": 0.0}


PROVIDERS = {
    "prospeo": {"cost": 0.01, "lookup": _lookup_prospeo},
    "leadmagic": {"cost": 0.02, "lookup": _lookup_leadmagic},
    "null": {"cost": 0.00, "lookup": _lookup_null},
}


# ---------------------------------------------------------------- waterfall

def _lead_cache_key(lead: dict) -> str:
    """Stable key: name+company or email; identical leads never re-purchased."""
    if lead.get("email"):
        return f"email:{lead['email']}"
    return f"person:{lead.get('name', '')}|{lead.get('company', '')}"


def _cache_path(state_dir, pipeline) -> "Path":
    d = Path(state_dir) / "enrich_cache"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{pipeline or 'default'}.cache.json"


def run_waterfall(lead: dict, provider_order: list[str], config: dict,
                  state_dir: str | None = None, pipeline: str | None = None) -> WaterfallResult:
    """Run one lead through the cost-ordered waterfall. Logs every call.

    Cached leads (same email or name+company, seen in this state dir) return the
    stored answer for free — never buy the same person twice.
    """
    result = WaterfallResult()
    key = _lead_cache_key(lead)
    if state_dir is not None:
        cf = _cache_path(state_dir, pipeline)
        cache = json.loads(cf.read_text()) if cf.exists() else {}
        if key in cache:
            hit = cache[key]
            result.email = hit.get("email")
            result.provider = hit.get("provider")
            result.attempts.append({"provider": hit.get("provider"), "status": "cached"})
            return result
    for name in provider_order:
        if name not in PROVIDERS:
            result.attempts.append({"provider": name, "status": "unknown provider"})
            continue
        spec = PROVIDERS[name]
        try:
            out = spec["lookup"](lead, config)
        except Exception as e:
            result.attempts.append({"provider": name, "status": f"error: {e}"})
            continue
        if state_dir is not None:
            ledger.log_call(state_dir, name, "email_find", out.get("cost", spec["cost"]),
                            rows=1, pipeline=pipeline)
        result.cost_usd += out.get("cost", spec["cost"])
        if out.get("email"):
            result.email = out["email"]
            result.provider = name
            result.attempts.append({"provider": name, "status": "hit"})
            break
        result.attempts.append({"provider": name, "status": "miss"})
    if state_dir is not None:
        cf = _cache_path(state_dir, pipeline)
        cache = json.loads(cf.read_text()) if cf.exists() else {}
        cache[key] = {"email": result.email, "provider": result.provider}
        cf.write_text(json.dumps(cache, indent=2))
    return result


class BudgetExceeded(RuntimeError):
    """Raised when cumulative waterfall spend crosses the run budget."""


def enrich_rows(rows: list[dict], provider_order: list[str], config: dict,
                state_dir: str | None = None, pipeline: str | None = None,
                budget_usd: float | None = None) -> list[dict]:
    """Enrich every row; adds email/lead_source on hit, marks misses.

    budget_usd: hard cap on cumulative spend for this run. Crossing it raises
    BudgetExceeded (callers can catch and print a ledger summary).
    """
    out = []
    spent = 0.0
    for row in rows:
        r = run_waterfall(row, provider_order, config, state_dir=state_dir, pipeline=pipeline)
        spent += r.cost_usd
        if budget_usd is not None and spent > budget_usd:
            raise BudgetExceeded(
                f"budget exceeded: spent ${spent:.4f} of ${budget_usd:.4f} cap "
                f"after {len(out)} rows enriched"
            )
        enriched = dict(row)
        if r.ok:
            enriched["email"] = r.email
            enriched["enrich_provider"] = r.provider
        else:
            enriched["enrich_status"] = "miss"
        enriched["enrich_cost_usd"] = round(r.cost_usd, 4)
        out.append(enriched)
    return out
