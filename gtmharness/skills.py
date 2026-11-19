"""Skill registry — Graphed's "skills are templates" idea, local-first.

A skill is a reusable pipeline template with parameter slots. Ship starter
skills, let users drop their own into ~/.gtmharness/skills/ and share them as
plain YAML files (no marketplace, no lock-in).
"""

from __future__ import annotations

from pathlib import Path

import yaml

SKILLS_DIR = Path.home() / ".gtmharness" / "skills"


def list_skills(extra_dir: str | Path | None = None) -> dict[str, dict]:
    """Load all skills from the built-in dir and the user dir."""
    skills: dict[str, dict] = {}
    for d in (Path(__file__).parent / "skills", SKILLS_DIR, Path(extra_dir) if extra_dir else None):
        if d is None or not d.exists():
            continue
        for f in sorted(d.glob("*.yaml")):
            raw = yaml.safe_load(f.read_text())
            if isinstance(raw, dict) and raw.get("name"):
                # YAML bare `params:\n  x\n  y` folds into one string; split it
                p = raw.get("params")
                if isinstance(p, str):
                    raw["params"] = p.split()
                skills[raw["name"]] = raw
    return skills


def render_skill(skill: dict, params: dict[str, str]) -> str:
    """Fill {{param}} slots in a skill's template; returns pipeline YAML.

    Renders only the template (not the whole skill) so the output can be saved
    directly as a pipeline YAML and round-trip through load_pipeline validation.
    """
    template = skill.get("template")
    if not template:
        raise ValueError("skill has no template")
    required = set(skill.get("params") or [])
    missing = required - set(params)
    if missing:
        raise ValueError(f"missing required params: {sorted(missing)}")
    template_str = yaml.dump(template, sort_keys=False)
    for k, v in params.items():
        template_str = template_str.replace("{{" + k + "}}", v)
    return template_str
