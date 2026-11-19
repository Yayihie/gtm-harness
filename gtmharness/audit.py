"""Append-only audit log.

The Reddit complaint: "If it writes under the rep's name, you can't filter its
changes in reports, you can't audit what it touched." Every harness write goes
to a JSONL log with actor=harness, timestamp, sink, key, and the exact fields.
"""

from __future__ import annotations

import json
import time
from pathlib import Path


def log_write(state_dir: str | Path, pipeline: str, sink: str, key: str,
              fields: dict, actor: str = "gtmharness") -> dict:
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor": actor,
        "pipeline": pipeline,
        "sink": sink,
        "key": key,
        "fields": fields,
    }
    with open(Path(state_dir) / "audit.jsonl", "a") as f:
        f.write(json.dumps(entry) + "\n")
    return entry


def read_log(state_dir: str | Path, pipeline: str | None = None) -> list[dict]:
    f = Path(state_dir) / "audit.jsonl"
    if not f.exists():
        return []
    entries = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
    if pipeline:
        entries = [e for e in entries if e["pipeline"] == pipeline]
    return entries
