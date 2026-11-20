"""Clay importer + adapters: Clay table schema -> pipeline YAML that validates."""
import json
import textwrap

import pytest
import yaml

from gtmharness.clay import ClayError, import_table, slugify
from gtmharness.cli import load_pipeline_str
from gtmharness.sources import load_rows


@pytest.fixture
def clay_schema():
    return {
        "name": "AI Startups Pipeline",
        "fields": [
            {"id": "f_email", "name": "Email", "type": "email"},
            {"id": "f_headcount", "name": "Headcount", "type": "number"},
            {"id": "f_founded", "name": "Founded", "type": "date"},
            {"id": "f_hiring", "name": "Is Hiring", "type": "checkbox"},
            {"id": "f_full", "name": "Full Name", "type": "text",
             "formulaText": "{{f_firstName}} + ' ' + {{f_lastName}}"},
            {"id": "f_res", "name": "Company Research", "type": "text",
             "prompt": "Research {Company Domain}", "model": "clay-neon"},
        ],
    }


def test_slugify():
    assert slugify("Work Email") == "work_email"
    assert slugify("  Company 2! ") == "company_2"
    assert slugify("") == "column"


def test_import_produces_valid_spec(clay_schema):
    p = import_table(clay_schema, name="ai_startups", source_csv="examples/clay_companies.csv")
    text = yaml.safe_dump(p, sort_keys=False)
    pipeline = load_pipeline_str(text)  # must pass the real spec validator
    assert pipeline.name == "ai_startups"
    sink = pipeline.sinks()[0]
    names = [f.name for f in sink.contract]
    assert names == ["email", "headcount", "founded", "is_hiring", "full_name", "company_research"]
    types = {f.name: f.type for f in sink.contract}
    assert types["headcount"] == "number"
    assert types["founded"] == "datetime"
    assert types["is_hiring"] == "boolean"
    assert types["email"] == "string"


def test_computed_columns_are_optional_and_documented(clay_schema):
    p = import_table(clay_schema)
    src = p["steps"][0]
    req = {f["name"]: f["required"] for f in p["steps"][-1]["contract"]}
    assert req["full_name"] is False
    assert req["company_research"] is False
    assert req["email"] is True
    computed = src["config"]["computed_columns"]
    assert computed["full_name"]["formulaText"] == "{{f_firstName}} + ' ' + {{f_lastName}}"
    assert computed["company_research"]["model"] == "clay-neon"


def test_field_map_covers_all_field_ids(clay_schema):
    p = import_table(clay_schema)
    fm = p["steps"][0]["config"]["field_map"]
    assert fm["f_email"] == "email"
    assert fm["f_company_research"] if False else fm["f_res"] == "company_research"


def test_duplicate_column_names_get_suffixes():
    schema = {"fields": [
        {"id": "f_a", "name": "Email", "type": "email"},
        {"id": "f_b", "name": "Email", "type": "email"},
    ]}
    p = import_table(schema)
    names = [f["name"] for f in p["steps"][-1]["contract"]]
    assert names == ["email", "email_1"]


def test_no_fields_raises():
    with pytest.raises(ClayError):
        import_table({"fields": []})


def test_bad_name_raises():
    with pytest.raises(ClayError):
        import_table({"fields": [{"name": "X", "type": "text"}]}, name="Bad Name!")


def test_bare_field_list_accepted():
    p = import_table([{"name": "Email", "type": "email"}])
    assert p["steps"][-1]["contract"][0]["name"] == "email"


def test_clay_csv_adapter(tmp_path):
    csv = tmp_path / "t.csv"
    csv.write_text("Email,Company Name\njane@acme.com,Acme\n")
    rows = load_rows("clay_csv", {"path": str(csv), "field_map": {"f_email": "Email"}})
    assert rows == [{"email": "jane@acme.com", "company_name": "Acme"}]


def test_clay_json_adapter_field_ids(tmp_path):
    recs = tmp_path / "r.json"
    recs.write_text(json.dumps([
        {"data": {"f_email": "jane@acme.com", "f_company": "Acme AI"}},
        {"data": {"f_email": "sam@corp.io", "f_company": "Corp"}},
    ]))
    rows = load_rows("clay_json", {"path": str(recs), "field_map": {"f_email": "Email", "f_company": "Company Name"}})
    assert rows[0] == {"email": "jane@acme.com", "company_name": "Acme AI"}


def test_clay_json_plain_records(tmp_path):
    recs = tmp_path / "r.json"
    recs.write_text(json.dumps([{"Email": "a@b.c"}]))
    rows = load_rows("clay_json", {"path": str(recs)})
    assert rows == [{"email": "a@b.c"}]


def test_end_to_end_example_spec():
    """The example fixture files round-trip: import -> load -> adapter reads rows."""
    schema = json.load(open("examples/clay_companies.json"))
    p = import_table(schema, name="ai_startups", source_csv="examples/clay_companies.csv")
    pipeline = load_pipeline_str(yaml.safe_dump(p, sort_keys=False))
    src = pipeline.sources()[0]
    rows = load_rows(src.using, src.config)
    assert len(rows) == 2
    assert rows[0]["email"] == "jane@acmeai.com"
    # Clay CSVs are all-text; the adapter coerces to the contract types.
    assert rows[0]["headcount"] == 42
    assert rows[1]["is_hiring"] is False
