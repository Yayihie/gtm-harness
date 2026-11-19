import pytest

from gtmharness.skills import list_skills, render_skill


def test_builtin_skills_load():
    found = list_skills()
    assert "inbound_lead_routing" in found
    assert found["inbound_lead_routing"]["params"] == ["source_path", "crm"]


def test_render_fills_params():
    found = list_skills()
    out = render_skill(found["inbound_lead_routing"], {"source_path": "leads.json", "crm": "crm"})
    assert "leads.json" in out
    assert "{{source_path}}" not in out


def test_render_missing_param_raises():
    found = list_skills()
    with pytest.raises(ValueError, match="missing required params"):
        render_skill(found["inbound_lead_routing"], {"source_path": "leads.json"})


def test_user_dir_overrides(tmp_path):
    (tmp_path / "my_skill.yaml").write_text("name: my_skill\ndescription: custom\nparams: []\n")
    found = list_skills(extra_dir=tmp_path)
    assert found["my_skill"]["description"] == "custom"
