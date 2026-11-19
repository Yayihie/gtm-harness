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

from . import audit, dryrun, schema
from .spec import SpecError, load_pipeline
from .sources import load_rows


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
        audit.log_write(args.state_dir, pipeline.name, w["sink"], w["key"], w["fields"])
        print(f"  wrote {w['sink']} <- {w['key']}")
    print(f"RUN OK — {len(plan_out['writes'])} writes audited to {args.state_dir}/audit.jsonl")
    return 0


def cmd_audit(args) -> int:
    entries = audit.read_log(args.state_dir, pipeline=args.pipeline)
    print(json.dumps(entries, indent=2))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gtmharness", description="CI/CD discipline for GTM pipelines")
    p.add_argument("--state-dir", default=".gtmharness")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in [("check", cmd_check), ("plan", cmd_plan), ("run", cmd_run), ("audit", cmd_audit)]:
        sp = sub.add_parser(name)
        sp.add_argument("pipeline", help="path to pipeline YAML")
        sp.set_defaults(fn=fn)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
