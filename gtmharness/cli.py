"""CLI: gtmharness check | plan | run | audit.

- check: validate spec + detect schema drift (the CI gate)
- plan:  dry-run, show the exact write set
- run:   write only after plan passes; every write is audited
- audit: read the log back
"""

from __future__ import annotations

import argparse
import json
import sys

from . import audit, dryrun, ledger, schema, skills
from .spec import SpecError, load_pipeline
from .sources import load_rows

SINK_DISPATCH = {
    "hubspot": ("gtmharness.adapters.hubspot", "write_rows"),
    "salesforce": ("gtmharness.adapters.salesforce", "write_rows"),
}


def _write_to_sink(sink, row):
    """Dispatch a row to a real sink adapter; 'null' just records the intent."""
    if sink.using == "null":
        return {"key": row.get("email"), "id": None, "status": "dry"}
    if sink.using in SINK_DISPATCH:
        import importlib
        mod_name, fn_name = SINK_DISPATCH[sink.using]
        try:
            mod = importlib.import_module(mod_name)
            return getattr(mod, fn_name)(sink.config, [row])[0]
        except RuntimeError as e:
            return {"key": row.get("email"), "id": None, "status": f"error: {e}"}
    return {"key": row.get("email"), "id": None, "status": f"error: unknown sink '{sink.using}'"}


def _source_rows(pipeline):
    src = pipeline.sources()[0]
    return load_rows(src.using, src.config)


def cmd_check(args) -> int:
    try:
        pipeline = load_pipeline(args.pipeline)
    except SpecError as e:
        print(f"SPEC ERROR: {e}")
        return 2
    rows = _source_rows(pipeline)
    src = pipeline.sources()[0]
    res = schema.check_drift(rows, f"{pipeline.name}/{src.name}", args.state_dir)
    print(f"CHECK pipeline={pipeline.name} source={src.name}")
    d = res["drift"]
    if d["added"]:
        print(f"  added fields:   {d['added']}")
    if d["removed"]:
        print(f"  REMOVED fields: {d['removed']}")
    if d["retyped"]:
        print(f"  RETYPED fields: {d['retyped']}")
    print("  OK" if res["ok"] else "  DRIFT DETECTED — fix the spec or the source before running")
    return 0 if res["ok"] else 1


def cmd_plan(args) -> int:
    try:
        pipeline = load_pipeline(args.pipeline)
    except SpecError as e:
        print(f"SPEC ERROR: {e}")
        return 2
    rows = _source_rows(pipeline)
    plan_out = dryrun.plan(pipeline, rows)
    print(dryrun.format_plan(plan_out))
    return 0 if plan_out["ok"] else 1


def cmd_run(args) -> int:
    try:
        pipeline = load_pipeline(args.pipeline)
    except SpecError as e:
        print(f"SPEC ERROR: {e}")
        return 2
    rows = _source_rows(pipeline)
    plan_out = dryrun.plan(pipeline, rows)
    if not plan_out["ok"]:
        print(dryrun.format_plan(plan_out))
        print("RUN ABORTED — contract violations. Nothing was written.")
        return 1
    for w in plan_out["writes"]:
        sink = next(s for s in pipeline.sinks() if s.name == w["sink"])
        result = _write_to_sink(sink, w["fields"])
        audit.log_write(args.state_dir, pipeline.name, w["sink"], w["key"], w["fields"])
        print(f"  wrote {w['sink']} <- {w['key']} ({result['status']})")
    print(f"RUN OK — {len(plan_out['writes'])} writes audited to {args.state_dir}/audit.jsonl")
    return 0


def cmd_audit(args) -> int:
    entries = audit.read_log(args.state_dir, pipeline=args.pipeline)
    print(json.dumps(entries, indent=2))
    return 0


def cmd_ledger(args) -> int:
    totals = ledger.summarize(args.state_dir)
    if not totals:
        print("no provider calls logged yet")
        return 0
    for provider, t in sorted(totals.items()):
        print(f"  {provider}: {t['calls']} calls, {t['rows']} rows, ${t['cost_usd']:.4f}")
    return 0


def cmd_skills(args) -> int:
    found = skills.list_skills(extra_dir=args.dir)
    if not found:
        print("no skills found (built-in + ~/.gtmharness/skills/)")
        return 1
    for name, s in found.items():
        print(f"  {name}: {s.get('description', '')}")
        params = s.get("params") or []
        if params:
            print(f"    params: {', '.join(params)}")
    return 0


def cmd_skill_render(args) -> int:
    found = skills.list_skills(extra_dir=args.dir)
    if args.skill not in found:
        print(f"unknown skill '{args.skill}'")
        return 1
    params = dict(kv.split("=", 1) for kv in (args.set or []))
    try:
        print(skills.render_skill(found[args.skill], params))
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gtmharness", description="CI/CD discipline for GTM pipelines")
    p.add_argument("--state-dir", default=".gtmharness")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in [("check", cmd_check), ("plan", cmd_plan), ("run", cmd_run), ("audit", cmd_audit)]:
        sp = sub.add_parser(name)
        sp.add_argument("pipeline", help="path to pipeline YAML")
        sp.set_defaults(fn=fn)
    sp = sub.add_parser("ledger", help="summarize BYO provider spend")
    sp.set_defaults(fn=cmd_ledger)
    sp = sub.add_parser("skills", help="list pipeline skill templates")
    sp.add_argument("--dir", default=None, help="extra skills dir")
    sp.set_defaults(fn=cmd_skills)
    sp = sub.add_parser("skill", help="render a skill template to YAML")
    sp.add_argument("skill", help="skill name")
    sp.add_argument("--set", nargs="*", default=None, help="param=value pairs")
    sp.add_argument("--dir", default=None, help="extra skills dir")
    sp.set_defaults(fn=cmd_skill_render)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
