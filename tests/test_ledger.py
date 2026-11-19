from gtmharness.ledger import log_call, read_ledger, summarize


def test_log_and_read(tmp_path):
    log_call(tmp_path, "prospeo", "email_find", 0.01, rows=1, pipeline="p1")
    log_call(tmp_path, "leadmagic", "email_find", 0.02, rows=2)
    entries = read_ledger(tmp_path)
    assert len(entries) == 2
    assert entries[0]["provider"] == "prospeo"


def test_filter_by_provider(tmp_path):
    log_call(tmp_path, "prospeo", "email_find", 0.01)
    log_call(tmp_path, "leadmagic", "email_find", 0.02)
    assert len(read_ledger(tmp_path, provider="prospeo")) == 1


def test_summarize_totals(tmp_path):
    log_call(tmp_path, "prospeo", "email_find", 0.01, rows=1)
    log_call(tmp_path, "prospeo", "email_find", 0.01, rows=1)
    totals = summarize(tmp_path)
    assert totals["prospeo"] == {"calls": 2, "rows": 2, "cost_usd": 0.02}


def test_empty(tmp_path):
    assert read_ledger(tmp_path) == []
    assert summarize(tmp_path) == {}
