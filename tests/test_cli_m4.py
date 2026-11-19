"""CLI tests for M4: diff, doctor, --verify, --json, snapshot-on-run."""
import json
import subprocess
import sys

from gtmharness.audit import verify_log
from gtmharness.rollback import read_snapshot

PIPE_A = """
name: diff_demo
steps:
  - name: leads
    kind: source
    using: json
    config: {path: leads.json}
  - name: out
    kind: sink
    using: dry
    contract:
      - {name: email, type: string}
"""

PIPE_B = """
name: diff_demo
steps:
  - name: leads
    kind: source
    using: json
    config: {path: leads.json}
"""

PIPE_C = """
name: diff_demo
steps:
  - name: leads
    kind: source
    using: json
    config: {path: leads.json}
  - name: out
    kind: sink
    using: dry
    contract:
      - {name: email, type: string}
      - {name: phone, type: string}
"""


def setup(tmp_path):
    (tmp_path / "a.yaml").write_text(PIPE_A)
    (tmp_path / "b.yaml").write_text(PIPE_B)
    (tmp_path / "c.yaml").write_text(PIPE_C)
    (tmp_path / "leads.json").write_text(json.dumps([{"email": "a@b.com"}]))


def run_cli(tmp_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "gtmharness.cli", "--state-dir", str(tmp_path / ".state"), *args],
        capture_output=True, text=True, cwd=str(tmp_path),
    )


def test_diff_no_changes(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "diff", "a.yaml", "a.yaml")
    assert r.returncode == 0
    assert "no changes" in r.stdout


def test_diff_removed_step_breaking(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "diff", "a.yaml", "b.yaml")
    assert r.returncode == 1
    assert "BREAKING" in r.stdout
    assert "removed step" in r.stdout


def test_diff_added_field_ok(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "diff", "a.yaml", "c.yaml")
    assert r.returncode == 0
    assert "contract +['phone']" in r.stdout


def test_doctor_pass(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "doctor", "a.yaml")
    assert r.returncode == 0, r.stdout
    assert "PASS" in r.stdout


def test_doctor_missing_source(tmp_path):
    (tmp_path / "a.yaml").write_text(PIPE_A.replace("leads.json", "nope.json"))
    r = run_cli(tmp_path, "doctor", "a.yaml")
    assert r.returncode == 1
    assert "FAIL" in r.stdout


def test_audit_verify_intact(tmp_path):
    setup(tmp_path)
    run_cli(tmp_path, "run", "a.yaml")
    r = run_cli(tmp_path, "audit", "a.yaml", "--verify")
    assert r.returncode == 0
    assert "INTACT" in r.stdout


def test_audit_verify_detects_tamper(tmp_path):
    setup(tmp_path)
    run_cli(tmp_path, "run", "a.yaml")
    log = tmp_path / ".state" / "audit.jsonl"
    lines = log.read_text().splitlines()
    entry = json.loads(lines[0])
    entry["key"] = "evil@x.com"
    lines[0] = json.dumps(entry)
    log.write_text("\n".join(lines) + "\n")
    r = run_cli(tmp_path, "audit", "a.yaml", "--verify")
    assert r.returncode == 1
    assert "TAMPER" in r.stdout or "mismatch" in r.stdout


def test_json_output_plan(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "--json", "plan", "a.yaml")
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d["command"] == "plan"
    assert d["ok"] is True


def test_json_output_check(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "--json", "check", "a.yaml")
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d["command"] == "check"
    assert d["ok"] is True


def test_run_creates_snapshot(tmp_path):
    setup(tmp_path)
    r = run_cli(tmp_path, "run", "a.yaml")
    assert r.returncode == 0, r.stdout
    snap = read_snapshot(tmp_path / ".state")
    assert snap["pipeline"] == "diff_demo"
    assert len(snap["writes"]) == 1


def test_plan_truncates_long_fields(tmp_path):
    setup(tmp_path)
    long_email = "x" * 200 + "@example.com"
    (tmp_path / "leads.json").write_text(json.dumps([{"email": long_email}]))
    r = run_cli(tmp_path, "plan", "a.yaml")
    assert r.returncode == 0
    assert "…" in r.stdout
    assert long_email not in r.stdout
