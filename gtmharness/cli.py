"""CLI: gtmharness check | plan | run | audit | diff | doctor | ledger | skills.

- check: validate spec + detect schema drift (the CI gate)
- plan:  dry-run, show the exact write set
- run:   write only after plan passes; every write is audited (hash-chained)
- diff:  show exactly what a spec change would alter
- doctor: validate credentials, adapters, and state dir health
- audit: read the log back (or verify the hash chain with --verify)
- --json: structured output mode for CI on every command
"""

from __future__ import annotations

import argparse
import json
import sys

from . import audit, doctor, dryrun, ledger, schema, skills, specdiff
from .spec import SpecError, load_pipeline
from .sources import load_rows

SINK_DISPATCH = {
    "hubspot": ("gtmharness.adapters.hubspot", "write_rows"),
    "salesforce": ("gtmharness.adapters.salesforce", "write_rows"),
    "webhook": ("gtmharness.adapters.webhook", "write_rows"),
}


def _write_to_sink(sink, row):
    """Dispatch a row to a real sink adapter; 'dry' just records the intent."""
    if sink.using == "dry":
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


def _apply_transforms(rows, pipeline, state_dir, budget_usd=None):
    """Execute transform steps in order. 'enrich' runs the BYO-key waterfall."""
    from .adapters import enrich
    for step in pipeline.steps:
        if step.kind != "transform":
            continue
        if step.using == "enrich":
            providers = step.config.get("providers") or ["dry"]
            pconfig = step.config.get("provider_config") or {}
            budget = step.config.get("budget_usd") or budget_usd
            rows = enrich.enrich_rows(rows, providers, pconfig,
                                      state_dir=state_dir,
                                      pipeline=pipeline.name,
                                      budget_usd=budget)
        else:
            raise ValueError(f"transform '{step.name}': unknown adapter '{step.using}'")
    return rows


def _load(args):
    try:
        return load_pipeline(args.pipeline)
    except SpecError as e:
        print(f"SPEC ERROR: {e}")
        return None


def cmd_check(args) -> int:
    pipeline = _load(args)
    if pipeline is None:
        return 2
    rows = _source_rows(pipeline)
    src = pipeline.sources()[0]
    res = schema.check_drift(rows, f"{pipeline.name}/{src.name}", args.state_dir)
    if args.json:
        print(json.dumps({"command": "check", "pipeline": pipeline.name,
                          "source": src.name, **res}))
    else:
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
    pipeline = _load(args)
    if pipeline is None:
        return 2
    rows = _source_rows(pipeline)
    plan_out = dryrun.plan(pipeline, rows)
    if args.json:
        print(json.dumps({"command": "plan", **plan_out}))
    else:
        print(dryrun.format_plan(plan_out))
    return 0 if plan_out["ok"] else 1


def cmd_run(args) -> int:
    pipeline = _load(args)
    if pipeline is None:
        return 2
    rows = _source_rows(pipeline)
    try:
        rows = _apply_transforms(rows, pipeline, args.state_dir, budget_usd=args.budget)
    except Exception as e:
        if args.json:
            print(json.dumps({"command": "run", "ok": False, "error": str(e)}))
        else:
            print(f"TRANSFORM ERROR: {e}")
            totals = ledger.summarize(args.state_dir)
            if totals:
                print("  ledger so far:")
                for provider, t in sorted(totals.items()):
                    print(f"    {provider}: {t['calls']} calls, {t['rows']} rows, ${t['cost_usd']:.4f}")
            print("RUN ABORTED — nothing was written.")
        return 1
    plan_out = dryrun.plan(pipeline, rows)
    if not plan_out["ok"]:
        if args.json:
            print(json.dumps({"command": "run", "ok": False, "errors": plan_out["errors"]}))
        else:
            print(dryrun.format_plan(plan_out))
            print("RUN ABORTED — contract violations. Nothing was written.")
        return 1
    from . import rollback
    for w in plan_out["writes"]:
        sink = next(s for s in pipeline.sinks() if s.name == w["sink"])
        result = _write_to_sink(sink, w["fields"])
        w["result_ids"] = [result["id"]] if result.get("id") else []
        audit.log_write(args.state_dir, pipeline.name, w["sink"], w["key"], w["fields"])
        if not args.json:
            print(f"  wrote {w['sink']} <- {w['key']} ({result['status']})")
    rollback.snapshot(args.state_dir, pipeline.name, plan_out["writes"])
    if args.json:
        print(json.dumps({"command": "run", "ok": True, "writes": len(plan_out["writes"]),
                          "state_dir": args.state_dir}))
    else:
        print(f"RUN OK — {len(plan_out['writes'])} writes audited to {args.state_dir}/audit.jsonl")
    return 0


def cmd_audit(args) -> int:
    if args.verify:
        res = audit.verify_log(args.state_dir)
        if args.json:
            print(json.dumps({"command": "audit", "verify": res}))
        else:
            print("AUDIT LOG " + ("INTACT" if res["ok"] else f"TAMPERED — {res['reason']}"))
        return 0 if res["ok"] else 1
    entries = audit.read_log(args.state_dir, pipeline=args.pipeline)
    if args.json:
        print(json.dumps({"command": "audit", "entries": entries}))
    else:
        print(json.dumps(entries, indent=2))
    return 0


def cmd_diff(args) -> int:
    try:
        old = load_pipeline(args.old)
        new = load_pipeline(args.new)
    except SpecError as e:
        print(f"SPEC ERROR: {e}")
        return 2
    d = specdiff.diff_pipelines(old, new)
    if args.json:
        print(json.dumps({"command": "diff", **d}))
    else:
        print(specdiff.format_diff(d))
    return 1 if d["breaking"] else 0


def cmd_doctor(args) -> int:
    pipeline = _load(args)
    if pipeline is None:
        return 2
    res = doctor.doctor(pipeline, args.state_dir)
    if args.json:
        print(json.dumps({"command": "doctor", **res}))
    else:
        print(doctor.format_doctor(res))
    return 0 if res["ok"] else 1


def cmd_ledger(args) -> int:
    totals = ledger.summarize(args.state_dir)
    if args.json:
        print(json.dumps({"command": "ledger", "totals": totals}))
    else:
        if not totals:
            print("no provider calls logged yet")
            return 0
        for provider, t in sorted(totals.items()):
            print(f"  {provider}: {t['calls']} calls, {t['rows']} rows, ${t['cost_usd']:.4f}")
    return 0


def cmd_skills(args) -> int:
    found = skills.list_skills(extra_dir=args.dir)
    if args.json:
        print(json.dumps({"command": "skills",
                          "skills": {k: {"description": s.get("description", ""),
                                         "params": s.get("params", [])}
                                     for k, s in found.items()}}))
    else:
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
        rendered = skills.render_skill(found[args.skill], params)
        load_pipeline_str(rendered)  # round-trip validation
    except ValueError as e:
        print(f"ERROR: {e}")
        return 1
    except SpecError as e:
        print(f"RENDERED SPEC ERROR: {e}")
        return 1
    if args.json:
        print(json.dumps({"command": "skill_render", "skill": args.skill, "ok": True}))
    else:
        print(rendered)
    return 0


def load_pipeline_str(yaml_str):
    import yaml
    from .spec import load_pipeline as _load
    import tempfile, os
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        f.write(yaml_str)
        path = f.name
    try:
        return _load(path)
    finally:
        os.unlink(path)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="gtmharness", description="CI/CD discipline for GTM pipelines")
    p.add_argument("--state-dir", default=".gtmharness")
    p.add_argument("--json", action="store_true", help="structured output for CI")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in [("check", cmd_check), ("plan", cmd_plan), ("run", cmd_run), ("audit", cmd_audit)]:
        sp = sub.add_parser(name)
        sp.add_argument("pipeline", help="path to pipeline YAML")
        sp.set_defaults(fn=fn)
    sub.choices["run"].add_argument("--budget", type=float, default=None,
                                    help="max USD spend on enrichment this run")
    sub.choices["audit"].add_argument("--verify", action="store_true",
                                      help="verify the audit log hash chain")
    sp = sub.add_parser("diff", help="show what a spec change would alter")
    sp.add_argument("old", help="old pipeline YAML")
    sp.add_argument("new", help="new pipeline YAML")
    sp.set_defaults(fn=cmd_diff)
    sp = sub.add_parser("doctor", help="validate credentials, adapters, state dir")
    sp.add_argument("pipeline", help="path to pipeline YAML")
    sp.set_defaults(fn=cmd_doctor)
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
