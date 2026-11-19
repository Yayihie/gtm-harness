import pytest

from gtmharness.spec import FieldContract, Pipeline, Step
from gtmharness.specdiff import contract_diff, diff_pipelines, format_diff


def _mk(name, kind, using, contract=None):
    return Step(name=name, kind=kind, using=using, contract=contract or [])


def _pipe(name, steps):
    return Pipeline(name=name, steps=steps)


def test_no_changes():
    a = _pipe("p", [_mk("s", "source", "json"), _mk("out", "sink", "dry")])
    b = _pipe("p", [_mk("s", "source", "json"), _mk("out", "sink", "dry")])
    d = diff_pipelines(a, b)
    assert not d["breaking"]
    assert d["summary"] == ["no changes"]


def test_added_step_not_breaking():
    a = _pipe("p", [_mk("s", "source", "json")])
    b = _pipe("p", [_mk("s", "source", "json"), _mk("out", "sink", "dry")])
    d = diff_pipelines(a, b)
    assert not d["breaking"]
    assert "added step 'out'" in d["summary"]


def test_removed_step_breaking():
    a = _pipe("p", [_mk("s", "source", "json"), _mk("out", "sink", "dry")])
    b = _pipe("p", [_mk("s", "source", "json")])
    d = diff_pipelines(a, b)
    assert d["breaking"]
    assert "removed step 'out'" in d["summary"]


def test_adapter_change_breaking():
    a = _pipe("p", [_mk("s", "source", "json"), _mk("out", "sink", "dry")])
    b = _pipe("p", [_mk("s", "source", "json"), _mk("out", "sink", "webhook")])
    d = diff_pipelines(a, b)
    assert d["breaking"]  # sink adapter changed
    assert "adapter changed" in d["summary"][0]


def test_contract_added_field():
    a = _pipe("p", [_mk("out", "sink", "dry", [FieldContract("email")])])
    b = _pipe("p", [_mk("out", "sink", "dry", [FieldContract("email"), FieldContract("phone")])])
    d = diff_pipelines(a, b)
    assert not d["breaking"]  # adding fields to the contract is not breaking
    assert "contract +['phone']" in d["summary"][0]


def test_contract_removed_field_breaking():
    a = _pipe("p", [_mk("out", "sink", "dry", [FieldContract("email"), FieldContract("phone")])])
    b = _pipe("p", [_mk("out", "sink", "dry", [FieldContract("email")])])
    d = diff_pipelines(a, b)
    assert d["breaking"]
    assert "contract -['phone']" in d["summary"][0]


def test_contract_type_change_breaking():
    a = _pipe("p", [_mk("out", "sink", "dry", [FieldContract("n", type="number")])])
    b = _pipe("p", [_mk("out", "sink", "dry", [FieldContract("n", type="string")])])
    d = diff_pipelines(a, b)
    assert d["breaking"]
    assert "contract field 'n'" in d["summary"][0]


def test_contract_diff_types():
    cd = contract_diff([FieldContract("x")], [FieldContract("x", type="number")])
    assert cd["changed"]["x"]["new"]["type"] == "number"


def test_format_diff_shows_breaking():
    a = _pipe("p", [_mk("s", "source", "json"), _mk("out", "sink", "dry")])
    b = _pipe("p", [_mk("s", "source", "json")])
    d = diff_pipelines(a, b)
    s = format_diff(d)
    assert "BREAKING" in s
