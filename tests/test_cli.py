import json
import subprocess
import sys
from pathlib import Path

PIPE = """
name: demo_pipeline
steps:
  - name: leads
    kind: source
    using: json
    config: {path: leads.json}
  - name: to_crm
    kind: sink
    using: crm
    contract:
      - {name: email, type: string}
      - {name: lead_source, type: string, enum: [paid, organic, event]}
"""


def setup(tmp_path):
    (tmp_path / "pipe.yaml").write_text(PIPE)
    (tmp_path / "leads.json").write_text(json.dumps([
        {"email": "a@b.com", "lead_source": "paid"},
        {"email": "bad@x.com", "lead_source": "free"},
    ]))


def run_cli(tmp_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "gtmharness.cli", "--state-dir", str(tmp_path / ".state"), *args],
        capture_output=True, text=True, cwd=str(tmp_path),
    )


def test_plan_blocks_contract_violation(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "plan", "pipe.yaml")
    assert r.returncode == 1
    assert "BLOCK" in r.stdout and "not in enum" in r.stdout


def test_run_aborts_writes_nothing(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "run", "pipe.yaml")
    assert r.returncode == 1
    assert "ABORTED" in r.stdout
    assert not (tmp_path / ".state" / "audit.jsonl").exists()


def test_check_then_clean_run_audits(tmp_path):
    setup(tmp_path)
    (tmp_path / "leads.json").write_text(json.dumps([
        {"email": "a@b.com", "lead_source": "paid"},
    ]))
    r = run_cli(tmp_path, "check", "pipe.yaml")
    assert r.returncode == 0, r.stdout
    r = run_cli(tmp_path, "run", "pipe.yaml")
    assert r.returncode == 0, r.stdout
    audit = json.loads((tmp_path / ".state" / "audit.jsonl").read_text().splitlines()[0])
    assert audit["actor"] == "gtmharness"
    assert audit["pipeline"] == "demo_pipeline"


def test_check_detects_renamed_field(tmp_path):
    setup(tmp_path)
    (tmp_path / "leads.json").write_text(json.dumps([
        {"email": "a@b.com", "lead_source": "paid"},
    ]))
    run_cli(tmp_path, "check", "pipe.yaml")  # baseline snapshot
    (tmp_path / "leads.json").write_text(json.dumps([
        {"email": "a@b.com", "source": "paid"},   # renamed upstream!
    ]))
    r = run_cli(tmp_path, "check", "pipe.yaml")
    assert r.returncode == 1
    assert "REMOVED" in r.stdout
