import json
from pathlib import Path

from gtmharness.audit import log_write, read_log, verify_log


def test_chain_intact_after_writes(tmp_path):
    log_write(tmp_path, "p1", "crm", "a@b.com", {"email": "a@b.com"})
    log_write(tmp_path, "p1", "crm", "c@d.com", {"email": "c@d.com"})
    log_write(tmp_path, "p2", "crm", "e@f.com", {"email": "e@f.com"})
    res = verify_log(tmp_path)
    assert res["ok"]
    assert res["first_bad_index"] is None


def test_edit_breaks_chain(tmp_path):
    log_write(tmp_path, "p1", "crm", "a@b.com", {"email": "a@b.com"})
    log_write(tmp_path, "p1", "crm", "c@d.com", {"email": "c@d.com"})
    f = Path(tmp_path) / "audit.jsonl"
    lines = f.read_text().splitlines()
    entry = json.loads(lines[0])
    entry["fields"]["email"] = "tampered@evil.com"
    lines[0] = json.dumps(entry)
    f.write_text("\n".join(lines) + "\n")
    res = verify_log(tmp_path)
    assert not res["ok"]
    assert res["first_bad_index"] == 0


def test_delete_breaks_chain(tmp_path):
    log_write(tmp_path, "p1", "crm", "a@b.com", {})
    log_write(tmp_path, "p1", "crm", "c@d.com", {})
    log_write(tmp_path, "p1", "crm", "e@f.com", {})
    f = Path(tmp_path) / "audit.jsonl"
    lines = f.read_text().splitlines()
    del lines[1]  # remove the middle entry
    f.write_text("\n".join(lines) + "\n")
    res = verify_log(tmp_path)
    assert not res["ok"]
    assert res["first_bad_index"] == 1


def test_empty_log_verifies(tmp_path):
    res = verify_log(tmp_path)
    assert res["ok"]


def test_read_log_filter_still_works(tmp_path):
    log_write(tmp_path, "p1", "crm", "a@b.com", {})
    log_write(tmp_path, "p2", "crm", "c@d.com", {})
    assert len(read_log(tmp_path, pipeline="p1")) == 1
