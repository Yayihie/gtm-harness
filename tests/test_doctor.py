import json
from pathlib import Path

from gtmharness.doctor import doctor, format_doctor
from gtmharness.spec import Pipeline, Step


def _pipe(source_path, sink_using="dry"):
    return Pipeline(name="p", steps=[
        Step(name="s", kind="source", using="json", config={"path": source_path}),
        Step(name="out", kind="sink", using=sink_using),
    ])


def test_doctor_all_pass(tmp_path):
    (tmp_path / "leads.json").write_text("[]")
    d = doctor(_pipe(str(tmp_path / "leads.json")), tmp_path / ".state")
    assert d["ok"]
    assert all(c[1] for c in d["checks"])


def test_doctor_missing_source(tmp_path):
    d = doctor(_pipe(str(tmp_path / "nope.json")), tmp_path / ".state")
    assert not d["ok"]
    assert any(c[0] == "source_path" and not c[1] for c in d["checks"])


def test_doctor_state_dir_writable(tmp_path):
    (tmp_path / "leads.json").write_text("[]")
    d = doctor(_pipe(str(tmp_path / "leads.json")), tmp_path / ".state")
    assert any(c[0] == "state_dir" and c[1] for c in d["checks"])


def test_doctor_corrupt_snapshot(tmp_path):
    (tmp_path / "leads.json").write_text("[]")
    sd = tmp_path / ".state" / "p"
    sd.mkdir(parents=True)
    (sd / "s.schema.json").write_text("not json")
    d = doctor(_pipe(str(tmp_path / "leads.json")), tmp_path / ".state")
    assert not d["ok"]


def test_doctor_format():
    d = {"ok": True, "checks": [("source_path", True, "exists"), ("state_dir", True, "writable")]}
    s = format_doctor(d)
    assert "PASS" in s and "OK" in s
