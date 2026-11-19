from gtmharness.audit import log_write, read_log


def test_log_write_and_read(tmp_path):
    log_write(tmp_path, "p1", "crm", "a@b.com", {"email": "a@b.com"})
    log_write(tmp_path, "p2", "crm", "c@d.com", {"email": "c@d.com"})
    entries = read_log(tmp_path)
    assert len(entries) == 2
    assert entries[0]["actor"] == "gtmharness"
    assert entries[0]["pipeline"] == "p1"
    assert entries[0]["ts"].endswith("Z")


def test_read_log_filter(tmp_path):
    log_write(tmp_path, "p1", "crm", "a@b.com", {})
    log_write(tmp_path, "p2", "crm", "c@d.com", {})
    assert len(read_log(tmp_path, pipeline="p1")) == 1


def test_read_log_empty(tmp_path):
    assert read_log(tmp_path) == []
