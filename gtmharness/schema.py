"""Schema snapshots + drift detection.

The Reddit complaint: "six months later a field gets renamed upstream and the
routing quietly breaks." So the harness snapshots the observed schema of every
source and diffs it against the last snapshot. Removed/renamed/re-typed fields
=> loud failure before anything writes.
"""

from __future__ import annotations

import json
from pathlib import Path


def infer_schema(rows: list[dict]) -> dict[str, str]:
    """Infer a simple schema {field: type} from rows."""
    schema: dict[str, str] = {}
    for row in rows:
        for k, v in row.items():
            if v is None:
                continue
            t = "string"
            if isinstance(v, bool):
                t = "boolean"
            elif isinstance(v, (int, float)):
                t = "number"
            schema.setdefault(k, t)
    return schema


def snapshot(rows: list[dict], source_name: str, state_dir: str | Path) -> dict:
    """Save the current schema snapshot; return {prev, current}."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    f = state_dir / f"{source_name}.schema.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    current = infer_schema(rows)
    prev = json.loads(f.read_text()) if f.exists() else None
    f.write_text(json.dumps(current, indent=2, sort_keys=True))
    return {"prev": prev, "current": current}


def diff_schema(prev: dict | None, current: dict) -> dict:
    """Categorize drift: added, removed, retyped. Removed/retyped are breaking."""
    if prev is None:
        return {"added": sorted(current), "removed": [], "retyped": []}
    added = sorted(set(current) - set(prev))
    removed = sorted(set(prev) - set(current))
    retyped = sorted(k for k in set(prev) & set(current) if prev[k] != current[k])
    return {"added": added, "removed": removed, "retyped": retyped}


def check_drift(rows: list[dict], source_name: str, state_dir: str | Path) -> dict:
    """Snapshot + diff. Returns {'ok': bool, 'drift': {...}}."""
    snap = snapshot(rows, source_name, state_dir)
    drift = diff_schema(snap["prev"], snap["current"])
    return {"ok": not drift["removed"] and not drift["retyped"], "drift": drift}
