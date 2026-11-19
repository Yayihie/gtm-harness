"""Pipeline spec: GTM workflows declared as code (YAML), validated at load time.

A pipeline is a list of steps. Each step reads from a source and writes to a
sink under a field contract. Contracts are the point: if an upstream field is
renamed/removed, the harness fails loudly instead of silently breaking routing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

VALID_KINDS = {"source", "transform", "sink"}
VALID_SINKS = {"webhook", "hubspot", "salesforce", "dry"}
NAME_RE = re.compile(r"^[a-z0-9_]+$")


class SpecError(ValueError):
    """Raised when a pipeline spec is invalid."""


@dataclass
class FieldContract:
    name: str
    type: str = "string"          # string | number | boolean | datetime
    required: bool = True
    enum: list[str] = field(default_factory=list)  # picklist values


@dataclass
class Step:
    name: str
    kind: str                      # source | transform | sink
    using: str                     # adapter name, e.g. csv, json, webhook, crm
    config: dict = field(default_factory=dict)
    contract: list[FieldContract] = field(default_factory=list)


@dataclass
class Pipeline:
    name: str
    steps: list[Step]

    def sources(self) -> list[Step]:
        return [s for s in self.steps if s.kind == "source"]

    def sinks(self) -> list[Step]:
        return [s for s in self.steps if s.kind == "sink"]


def parse_contract(raw: dict) -> FieldContract:
    if not isinstance(raw, dict) or "name" not in raw:
        raise SpecError(f"contract entry must be a mapping with a 'name' key: {raw!r}")
    fc = FieldContract(
        name=str(raw["name"]),
        type=str(raw.get("type", "string")),
        required=bool(raw.get("required", True)),
        enum=list(raw.get("enum", [])),
    )
    if fc.type not in {"string", "number", "boolean", "datetime"}:
        raise SpecError(f"field '{fc.name}': unknown type '{fc.type}'")
    if fc.enum and fc.type != "string":
        raise SpecError(f"field '{fc.name}': enum requires type 'string'")
    return fc


def load_pipeline(path: str | Path) -> Pipeline:
    raw = yaml.safe_load(Path(path).read_text())
    if not isinstance(raw, dict):
        raise SpecError("pipeline file must be a YAML mapping")
    name = raw.get("name")
    if not name or not NAME_RE.match(str(name)):
        raise SpecError("pipeline needs a 'name' of [a-z0-9_]")
    steps_raw = raw.get("steps") or []
    if not steps_raw:
        raise SpecError("pipeline must declare at least one step")
    steps: list[Step] = []
    seen: set[str] = set()
    for i, s in enumerate(steps_raw):
        if not isinstance(s, dict):
            raise SpecError(f"step #{i + 1} must be a mapping")
        step_name = s.get("name")
        if not step_name or not NAME_RE.match(str(step_name)):
            raise SpecError(f"step #{i + 1}: 'name' must be [a-z0-9_]")
        if step_name in seen:
            raise SpecError(f"duplicate step name '{step_name}'")
        seen.add(step_name)
        kind = s.get("kind")
        if kind not in VALID_KINDS:
            raise SpecError(f"step '{step_name}': kind must be one of {sorted(VALID_KINDS)}")
        using = s.get("using")
        if not using:
            raise SpecError(f"step '{step_name}': missing 'using'")
        if kind == "sink" and using not in VALID_SINKS:
            raise SpecError(f"step '{step_name}': sink 'using' must be one of {sorted(VALID_SINKS)}")
        contract = [parse_contract(c) for c in (s.get("contract") or [])]
        if kind == "sink" and not contract:
            raise SpecError(f"step '{step_name}': sinks must declare a field contract")
        steps.append(Step(name=step_name, kind=kind, using=using,
                          config=dict(s.get("config") or {}), contract=contract))
    if not steps[0].kind == "source":
        raise SpecError("first step must be a source")
    return Pipeline(name=name, steps=steps)
