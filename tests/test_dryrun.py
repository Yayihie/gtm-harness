from gtmharness.dryrun import format_plan, plan, validate_contract
from gtmharness.spec import FieldContract


def test_validate_contract_missing_required():
    errs = validate_contract({"email": ""}, [FieldContract("email")])
    assert errs == ["missing required field 'email'"]


def test_validate_contract_enum_violation():
    errs = validate_contract(
        {"lead_source": "hackernews"},
        [FieldContract("lead_source", enum=["paid", "organic"])],
    )
    assert len(errs) == 1 and "not in enum" in errs[0]


def test_validate_contract_type_mismatch():
    errs = validate_contract({"n": "5"}, [FieldContract("n", type="number")])
    assert "expected number" in errs[0]


def test_plan_blocks_bad_rows():
    contract = [FieldContract("email"), FieldContract("lead_source", enum=["paid", "organic"])]
    sink = type("S", (), {"name": "to_crm", "using": "crm", "contract": contract})()
    pipeline = type("P", (), {"name": "p", "sinks": lambda self: [sink]})()
    rows = [
        {"email": "a@b.com", "lead_source": "paid"},
        {"email": "c@d.com", "lead_source": "free"},
    ]
    out = plan(pipeline, rows)
    assert not out["ok"]
    assert out["writes"][0]["errors"] == []
    assert out["writes"][1]["errors"]


def test_format_plan_shows_write_and_block():
    out = {
        "pipeline": "p", "rows_in": 2, "writes": [
            {"sink": "crm", "using": "crm", "row": 0, "key": "a@b.com",
             "fields": {"email": "a@b.com"}, "errors": []},
        ], "errors": [],
    }
    s = format_plan(out)
    assert "WRITE" in s and "a@b.com" in s
