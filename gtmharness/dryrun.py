"""Dry-run: simulate the pipeline and show exactly what WOULD change in the CRM.

The Reddit complaint: builds are handed over as "a Loom video and a Clay table
nobody else understands." `gtmharness plan` makes the change set visible and
reviewable before anything is written.
"""

from __future__ import annotations

from .spec import FieldContract, Pipeline


def validate_contract(row: dict, contract: list[FieldContract]) -> list[str]:
    """Return a list of contract violations for one row."""
    errors = []
    for fc in contract:
        if fc.name not in row or row[fc.name] is None or row[fc.name] == "":
            if fc.required:
                errors.append(f"missing required field '{fc.name}'")
            continue
        v = row[fc.name]
        if fc.type == "number" and not isinstance(v, (int, float)):
            errors.append(f"field '{fc.name}': expected number, got {type(v).__name__}")
        elif fc.type == "boolean" and not isinstance(v, bool):
            errors.append(f"field '{fc.name}': expected boolean, got {type(v).__name__}")
        elif fc.enum and str(v) not in fc.enum:
            errors.append(f"field '{fc.name}': value {v!r} not in enum {fc.enum}")
    return errors


def plan(pipeline: Pipeline, rows: list[dict]) -> dict:
    """Simulate writes for every sink. Returns a reviewable plan."""
    plan_out = {"pipeline": pipeline.name, "rows_in": len(rows), "writes": [], "errors": []}
    for sink in pipeline.sinks():
        for i, row in enumerate(rows):
            errors = validate_contract(row, sink.contract)
            write = {
                "sink": sink.name,
                "using": sink.using,
                "row": i,
                "key": row.get("id") or row.get("email") or f"row_{i}",
                "fields": {fc.name: row.get(fc.name) for fc in sink.contract if fc.name in row},
                "errors": errors,
            }
            plan_out["writes"].append(write)
            plan_out["errors"].extend(errors)
    plan_out["ok"] = not plan_out["errors"]
    return plan_out


FIELD_MAX_LEN = 60


def _trunc(v) -> str:
    """Format a field value; long values are truncated with an explicit ellipsis."""
    s = repr(v)
    if len(s) > FIELD_MAX_LEN:
        return s[:FIELD_MAX_LEN - 1] + "…"
    return s


def format_plan(plan_out: dict) -> str:
    lines = [
        f"PLAN  pipeline={plan_out['pipeline']}  rows_in={plan_out['rows_in']}  "
        f"writes={len(plan_out['writes'])}  errors={len(plan_out['errors'])}",
    ]
    for w in plan_out["writes"]:
        status = "WRITE " if not w["errors"] else "BLOCK "
        fields = "{" + ", ".join(f"{k}: {_trunc(v)}" for k, v in w["fields"].items()) + "}"
        lines.append(f"  [{status}] {w['sink']} <- {_trunc(w['key'])} {fields}")
        for e in w["errors"]:
            lines.append(f"         ! {e}")
    return "\n".join(lines)
