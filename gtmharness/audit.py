"""Append-only audit log with a rolling hash chain (tamper-evident).

Each entry carries `prev_hash` (the hash of the previous entry) and `hash`
(SHA-256 of the entry's own content + prev_hash). Editing or deleting any
entry breaks the chain and `verify_log` catches it.

The Reddit complaint: "If it writes under the rep's name, you can't filter its
changes in reports, you can't audit what it touched." This makes the log
provably intact — not just append-only.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

GENESIS_HASH = "0" * 64


def _entry_hash(entry: dict) -> str:
    """Hash the entry's content (excluding the hash field itself)."""
    content = {k: v for k, v in entry.items() if k != "hash"}
    serialized = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode()).hexdigest()


def log_write(state_dir: str | Path, pipeline: str, sink: str, key: str,
              fields: dict, actor: str = "gtmharness") -> dict:
    Path(state_dir).mkdir(parents=True, exist_ok=True)
    f = Path(state_dir) / "audit.jsonl"
    prev_hash = GENESIS_HASH
    if f.exists():
        lines = [l for l in f.read_text().splitlines() if l.strip()]
        if lines:
            try:
                prev_hash = json.loads(lines[-1])["hash"]
            except (json.JSONDecodeError, KeyError):
                prev_hash = GENESIS_HASH
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor": actor,
        "pipeline": pipeline,
        "sink": sink,
        "key": key,
        "fields": fields,
        "prev_hash": prev_hash,
    }
    entry["hash"] = _entry_hash(entry)
    with open(f, "a") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry


def read_log(state_dir: str | Path, pipeline: str | None = None) -> list[dict]:
    f = Path(state_dir) / "audit.jsonl"
    if not f.exists():
        return []
    entries = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
    if pipeline:
        entries = [e for e in entries if e["pipeline"] == pipeline]
    return entries


def verify_log(state_dir: str | Path) -> dict:
    """Verify the hash chain. Returns {'ok': bool, 'first_bad_index': int|None}."""
    entries = read_log(state_dir)
    prev = GENESIS_HASH
    for i, e in enumerate(entries):
        if e.get("prev_hash") != prev:
            return {"ok": False, "first_bad_index": i,
                    "reason": f"prev_hash mismatch at entry {i}"}
        expected = _entry_hash(e)
        if e.get("hash") != expected:
            return {"ok": False, "first_bad_index": i,
                    "reason": f"hash mismatch at entry {i} — content was edited"}
        prev = e["hash"]
    return {"ok": True, "first_bad_index": None, "reason": "chain intact"}
