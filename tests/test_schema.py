from gtmharness.schema import check_drift, diff_schema, infer_schema


def test_infer_schema_types():
    rows = [{"a": "x", "b": 1, "c": True, "d": None}]
    assert infer_schema(rows) == {"a": "string", "b": "number", "c": "boolean"}


def test_first_run_has_no_drift(tmp_path):
    res = check_drift([{"email": "a@b.com"}], "src", tmp_path)
    assert res["ok"]


def test_renamed_field_is_breaking(tmp_path):
    check_drift([{"email": "a@b.com", "lead_source": "paid"}], "src", tmp_path)
    res = check_drift([{"email": "a@b.com", "source": "paid"}], "src", tmp_path)
    assert not res["ok"]
    assert res["drift"]["removed"] == ["lead_source"]
    assert res["drift"]["added"] == ["source"]


def test_retyped_field_is_breaking(tmp_path):
    check_drift([{"count": "5"}], "src", tmp_path)
    res = check_drift([{"count": 5}], "src", tmp_path)
    assert not res["ok"]
    assert res["drift"]["retyped"] == ["count"]


def test_added_field_is_non_breaking(tmp_path):
    check_drift([{"email": "a@b.com"}], "src", tmp_path)
    res = check_drift([{"email": "a@b.com", "phone": "123"}], "src", tmp_path)
    assert res["ok"]
    assert res["drift"]["added"] == ["phone"]


def test_diff_none_prev():
    d = diff_schema(None, {"a": "string"})
    assert d == {"added": ["a"], "removed": [], "retyped": []}
