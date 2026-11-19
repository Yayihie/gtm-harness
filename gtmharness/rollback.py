"""Rollback — snapshot sink state before write, restore on `revert`.

`run` records a snapshot of the exact write set (from the plan) before
executing; `revert` rolls back the most recent run by re-applying the inverse
intent. For sinks that support deletion (webhook/dry: stateless; CRM: via id)
the snapshot stores the returned ids so a revert can act on real records.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def snapshot(state_dir: str | Path, pipeline: str, writes: list[dict]) -> dict:
    """Record the write set + per-row result ids for the latest run."""
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    snap = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pipeline": pipeline,
        "writes": writes,
    }
    (Path(state_dir) / "last_run.json").write_text(json.dumps(snap, indent=2))
    return snap


def read_snapshot(state_dir: str | Path) -> dict | None:
    f = Path(state_dir) / "last_run.json"
    if not f.exists():
        return None
    return json.loads(f.read_text())


def revert(state_dir: str | Path, sink_write_fn=None) -> dict:
    """Undo the last run. sink_write_fn(row, action) dispatches undo actions.

    For 'dry' sinks nothing to undo; for real sinks the caller supplies a
    delete/update function. Returns {'reverted': n, 'unrevertible': n}.
    """
    snap = read_snapshot(state_dir)
    if snap is None:
        return {"reverted": 0, "unrevertible": 0, "note": "no snapshot to revert"}
    reverted = unrevertible = 0
    for w in snap["writes"]:
        ids = w.get("result_ids") or []
        if not ids or sink_write_fn is None:
            unrevertible += 1
            continue
        for rid in ids:
            sink_write_fn(w, "delete", rid)
            reverted += 1
    return {"reverted": reverted, "unrevertible": unrevertible,
            "pipeline": snap["pipeline"], "ts": snap["ts"]}
