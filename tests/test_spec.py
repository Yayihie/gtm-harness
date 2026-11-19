from gtmharness.spec import SpecError, load_pipeline
import pytest


def test_valid_pipeline(tmp_path):
    p = tmp_path / "pipe.yaml"
    p.write_text("""
name: lead_routing
steps:
  - name: inbound_leads
    kind: source
    using: json
    config: {path: leads.json}
  - name: to_crm
    kind: sink
    using: dry
    contract:
      - {name: email, type: string}
      - {name: lead_source, type: string, enum: [paid, organic, event]}
""")
    pipe = load_pipeline(p)
    assert pipe.name == "lead_routing"
    assert len(pipe.steps) == 2
    assert pipe.sinks()[0].contract[0].name == "email"


def test_rejects_missing_contract_on_sink(tmp_path):
    p = tmp_path / "pipe.yaml"
    p.write_text("""
name: bad
steps:
  - name: s
    kind: source
    using: json
    config: {path: x.json}
  - name: sink
    kind: sink
    using: dry
""")
    with pytest.raises(SpecError, match="contract"):
        load_pipeline(p)


def test_rejects_first_step_not_source(tmp_path):
    p = tmp_path / "pipe.yaml"
    p.write_text("""
name: bad
steps:
  - name: sink
    kind: sink
    using: dry
    contract:
      - {name: email}
""")
    with pytest.raises(SpecError, match="source"):
        load_pipeline(p)


def test_rejects_bad_enum_type(tmp_path):
    p = tmp_path / "pipe.yaml"
    p.write_text("""
name: bad
steps:
  - name: s
    kind: source
    using: json
    config: {path: x.json}
  - name: sink
    kind: sink
    using: dry
    contract:
      - {name: n, type: number, enum: [1, 2]}
""")
    with pytest.raises(SpecError, match="enum"):
        load_pipeline(p)
