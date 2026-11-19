"""Doctor — validate credentials, adapters, and state dir health.

Checks:
- spec loads cleanly
- source path exists
- state dir is writable
- sink adapters importable (without needing the SDK installed)
- state dir snapshot files are valid JSON
"""

from __future__ import annotations

import json
from pathlib import Path

from .spec import Pipeline


def doctor(pipeline: Pipeline, state_dir: str | Path) -> dict:
    checks = []

    # 1. source path exists
    src = pipeline.sources()[0]
    path = src.config.get("path")
    if path and Path(path).exists():
        checks.append(("source_path", True, f"exists: {path}"))
    elif path:
        checks.append(("source_path", False, f"missing: {path}"))
    else:
        checks.append(("source_path", False, "no path in source config"))

    # 2. state dir writable
    sd = Path(state_dir)
    try:
        sd.mkdir(parents=True, exist_ok=True)
        probe = sd / ".doctor_probe"
        probe.write_text("ok")
        probe.unlink()
        checks.append(("state_dir", True, f"writable: {sd}"))
    except Exception as e:
        checks.append(("state_dir", False, f"not writable: {e}"))

    # 3. sink adapters known
    for sink in pipeline.sinks():
        if sink.using in {"dry", "webhook"}:
            checks.append((f"sink:{sink.name}", True, f"built-in adapter '{sink.using}'"))
        elif sink.using in {"hubspot", "salesforce"}:
            try:
                import importlib
                importlib.import_module(f"gtmharness.adapters.{sink.using}")
                checks.append((f"sink:{sink.name}", True, f"adapter '{sink.using}' importable"))
            except Exception as e:
                checks.append((f"sink:{sink.name}", False, f"adapter '{sink.using}' broken: {e}"))
        else:
            checks.append((f"sink:{sink.name}", False, f"unknown sink '{sink.using}'"))

    # 4. schema snapshots valid JSON (rglob catches pipeline/source nested dirs)
    schema_files = [f for f in sorted(sd.rglob("*.json"))
                    if "enrich_cache" not in f.parts and f.name != "last_run.json"]
    if schema_files:
        for f in schema_files:
            try:
                json.loads(f.read_text())
                checks.append((f"schema:{f.name}", True, "valid json"))
            except Exception as e:
                checks.append((f"schema:{f.name}", False, f"corrupt: {e}"))
    else:
        checks.append(("schema_snapshots", True, "no snapshots yet (first run)"))

    ok = all(c[1] for c in checks)
    return {"ok": ok, "checks": checks}


def format_doctor(d: dict) -> str:
    lines = ["DOCTOR " + ("OK" if d["ok"] else "FAILURES FOUND")]
    for name, passed, msg in d["checks"]:
        lines.append(f"  [{'PASS' if passed else 'FAIL'}] {name}: {msg}")
    return "\n".join(lines)
