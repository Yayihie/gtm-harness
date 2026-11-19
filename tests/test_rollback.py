from gtmharness.rollback import read_snapshot, revert, snapshot


def test_snapshot_and_read(tmp_path):
    snapshot(tmp_path, "p1", [{"sink": "out", "key": "a@b.com", "result_ids": ["x1"]}])
    snap = read_snapshot(tmp_path)
    assert snap["pipeline"] == "p1"
    assert snap["writes"][0]["result_ids"] == ["x1"]


def test_revert_no_snapshot(tmp_path):
    res = revert(tmp_path)
    assert res["reverted"] == 0
    assert "no snapshot" in res["note"]


def test_revert_deletes_ids(tmp_path):
    deleted = []
    snapshot(tmp_path, "p1", [
        {"sink": "out", "key": "a@b.com", "result_ids": ["id1", "id2"]},
        {"sink": "out", "key": "c@d.com", "result_ids": []},
    ])
    res = revert(tmp_path, sink_write_fn=lambda w, action, rid: deleted.append(rid))
    assert res["reverted"] == 2
    assert res["unrevertible"] == 1
    assert deleted == ["id1", "id2"]


def test_revert_no_sink_fn(tmp_path):
    snapshot(tmp_path, "p1", [{"sink": "out", "key": "a@b.com", "result_ids": ["id1"]}])
    res = revert(tmp_path)
    assert res["unrevertible"] == 1
