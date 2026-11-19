"""Cost ledger — Graphed's "one balance" idea, inverted for transparency.

Graphed charges 1 credit = 1 cent with no visibility into vendor cost. The
harness does the opposite: you bring your own provider keys, and every provider
call is logged with its real cost into an append-only ledger, so you always
know what enrichment actually costs you.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def log_call(state_dir: str | Path, provider: str, operation: str, cost_usd: float,
             rows: int = 1, pipeline: str | None = None) -> dict:
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "provider": provider,
        "operation": operation,
        "cost_usd": round(cost_usd, 6),
        "rows": rows,
        "pipeline": pipeline,
    }
    with open(Path(state_dir) / "ledger.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def read_ledger(state_dir: str | Path, provider: str | None = None) -> list[dict]:
    f = Path(state_dir) / "ledger.jsonl"
    if not f.exists():
        return []
    entries = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
    if provider:
        entries = [e for e in entries if e["provider"] == provider]
    return entries


def summarize(state_dir: str | Path) -> dict:
    """Totals by provider: {provider: {calls, rows, cost_usd}}."""
    totals: dict[str, dict] = {}
    for e in read_ledger(state_dir):
        t = totals.setdefault(e["provider"], {"calls": 0, "rows": 0, "cost_usd": 0.0})
        t["calls"] += 1
        t["rows"] += e["rows"]
        t["cost_usd"] = round(t["cost_usd"] + e["cost_usd"], 6)
    return totals
