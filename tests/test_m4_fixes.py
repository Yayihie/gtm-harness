"""Tests for the two M4 known-issue fixes: sink error policy + skills render validation."""
import json
import os
import subprocess
import sys

from gtmharness.spec import SpecError
from gtmharness.cli import load_pipeline_str

# The CLI runs as a subprocess, so the fake broken sink must be registered at
# interpreter start: both in the adapter namespace and in spec/cli validation.
SITECUSTOMIZE = """import gtmharness.spec as spec
from gtmharness.adapters import register


def broken_write_rows(config, rows):
    return [{"key": r.get("email"), "id": None,
             "status": "error: simulated CRM failure"} for r in rows]


register("broken", broken_write_rows)
spec.VALID_SINKS.add("broken")
"""

PIPE = """
name: sink_error_demo
steps:
  - name: leads
    kind: source
    using: json
    config: {path: leads.json}
  - name: out
    kind: sink
    using: broken
    contract:
      - {name: email, type: string}
"""

LEADS = [{"email": "a@b.com"}, {"email": "c@d.com"}]


def setup(tmp_path):
    (tmp_path / "pipe.yaml").write_text(PIPE)
    (tmp_path / "leads.json").write_text(json.dumps(LEADS))
    (tmp_path / "sitecustomize.py").write_text(SITECUSTOMIZE)


def run_cli(tmp_path, *args):
    env = dict(os.environ, PYTHONPATH=str(tmp_path))
    return subprocess.run(
        [sys.executable, "-m", "gtmharness.cli", "--state-dir", str(tmp_path / ".state"), *args],
        capture_output=True, text=True, cwd=str(tmp_path), env=env,
    )


def test_sink_error_reported_run_partial(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "run", "pipe.yaml")
    assert r.returncode == 1
    assert "RUN PARTIAL" in r.stdout
    assert "simulated CRM failure" in r.stdout


def test_sink_error_fail_fast(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "run", "pipe.yaml", "--fail-fast")
    assert r.returncode == 1
    assert r.stdout.count("wrote") == 1


def test_sink_error_json_output(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "--json", "run", "pipe.yaml")
    assert r.returncode == 1
    d = json.loads(r.stdout)
    assert d["ok"] is False
    assert len(d["errors"]) == 2


def test_skills_render_roundtrip_rejects_invalid():
    bad_skill = {
        "name": "bad_sink",
        "description": "renders an invalid pipeline",
        "params": ["sink_name"],
        "template": {
            "name": "bad_sink_pipeline",
            "steps": [
                {"name": "s", "kind": "source", "using": "json",
                 "config": {"path": "x.json"}},
                {"name": "out", "kind": "sink", "using": "{{sink_name}}",
                 "contract": [{"name": "email"}]},
            ],
        },
    }
    from gtmharness.skills import render_skill
    rendered = render_skill(bad_skill, {"sink_name": "not_a_real_sink"})
    try:
        load_pipeline_str(rendered)
        assert False, "expected SpecError for invalid sink"
    except SpecError as e:
        assert "must be one of" in str(e)


def test_skills_render_valid_template_loads():
    good_skill = {
        "name": "good",
        "description": "renders a valid pipeline",
        "params": ["path"],
        "template": {
            "name": "good_pipeline",
            "steps": [
                {"name": "s", "kind": "source", "using": "json",
                 "config": {"path": "{{path}}"}},
                {"name": "out", "kind": "sink", "using": "dry",
                 "contract": [{"name": "email"}]},
            ],
        },
    }
    from gtmharness.skills import render_skill
    rendered = render_skill(good_skill, {"path": "x.json"})
    pipeline = load_pipeline_str(rendered)
    assert pipeline.name == "good_pipeline"


def test_load_pipeline_str_valid():
    rendered = load_pipeline_str("""
name: ok
steps:
  - name: s
    kind: source
    using: json
    config: {path: x.json}
  - name: out
    kind: sink
    using: dry
    contract:
      - {name: email, type: string}
""")
    assert rendered.name == "ok"
