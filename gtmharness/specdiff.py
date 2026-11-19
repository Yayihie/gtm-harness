"""Spec diff — show exactly what a pipeline spec change would alter.

The Reddit complaint: "a field gets renamed upstream and the routing quietly
breaks." `gtmharness diff old.yaml new.yaml` makes the change explicit:
added/removed steps, changed contracts, changed adapters, changed sinks.
"""

from __future__ import annotations

from .spec import FieldContract, Pipeline


def contract_diff(old: list[FieldContract], new: list[FieldContract]) -> dict:
    o = {c.name: c for c in old}
    n = {c.name: c for c in new}
    added = sorted(set(n) - set(o))
    removed = sorted(set(o) - set(n))
    changed = {}
    for k in sorted(set(o) & set(n)):
        a, b = o[k], n[k]
        if (a.type, a.required, a.enum) != (b.type, b.required, b.enum):
            changed[k] = {
                "old": {"type": a.type, "required": a.required, "enum": a.enum},
                "new": {"type": b.type, "required": b.required, "enum": b.enum},
            }
    return {"added": added, "removed": removed, "changed": changed}


def _step_key(step):
    return (step.kind, step.using)


def diff_pipelines(old: Pipeline, new: Pipeline) -> dict:
    out = {"breaking": False, "summary": []}

    old_steps = {s.name: s for s in old.steps}
    new_steps = {s.name: s for s in new.steps}

    for name in sorted(set(new_steps) - set(old_steps)):
        out["summary"].append(f"added step '{name}'")
    for name in sorted(set(old_steps) - set(new_steps)):
        out["summary"].append(f"removed step '{name}'")
        out["breaking"] = True
    for name in sorted(set(old_steps) & set(new_steps)):
        a, b = old_steps[name], new_steps[name]
        if _step_key(a) != _step_key(b):
            out["summary"].append(
                f"step '{name}': adapter changed {a.using!r} -> {b.using!r}")
            out["breaking"] = True
        if a.kind != b.kind:
            out["summary"].append(
                f"step '{name}': kind changed {a.kind!r} -> {b.kind!r}")
            out["breaking"] = True
        if a.kind == "sink" and b.kind == "sink":
            cd = contract_diff(a.contract, b.contract)
            if cd["added"]:
                out["summary"].append(f"step '{name}': contract +{cd['added']}")
            if cd["removed"]:
                out["summary"].append(f"step '{name}': contract -{cd['removed']}")
                out["breaking"] = True
            for field, ch in cd["changed"].items():
                out["summary"].append(
                    f"step '{name}': contract field '{field}' changed "
                    f"{ch['old']} -> {ch['new']}")
                if ch["old"]["required"] and not ch["new"]["required"]:
                    pass  # loosening is not breaking
                else:
                    out["breaking"] = True
    if not out["summary"]:
        out["summary"].append("no changes")
    return out


def format_diff(d: dict) -> str:
    lines = ["BREAKING" if d["breaking"] else "OK"]
    for s in d["summary"]:
        lines.append(f"  {s}")
    return "\n".join(lines)
