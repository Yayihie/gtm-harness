"""Clay importer: convert a Clay table schema (clay_get_table JSON) into a
gtmharness pipeline YAML.

Clay's "config" is not YAML — it's the table schema Clay's MCP/API returns:
a fields list (text, number, date, checkbox, email, url, formula, AI, Claygent,
HTTP API, waterfall columns), a fieldGroupMap of waterfalls, and views. This
module maps that schema onto the two things gtmharness cares about:

1. a *source* step (clay_csv / clay_json adapter over the exported rows)
2. a *sink* field contract derived from the columns (types, computed flags)

The generated YAML must pass load_pipeline() unmodified — the importer is
just a projection, so any Clay table becomes a spec-valid pipeline. Formula
and AI/Claygent columns are preserved under the source step's
`computed_columns` config so nothing is lost on round-trip.
"""

from __future__ import annotations

import re
from typing import Any

CLAY_TYPES = {"string", "text", "email", "url", "number", "date", "checkbox", "boolean"}
TYPE_MAP = {
    "text": "string", "string": "string", "email": "string", "url": "string",
    "number": "number", "date": "datetime", "checkbox": "boolean", "boolean": "boolean",
}

SLUG_RE = re.compile(r"[^a-z0-9]+")
FORMULA_MARKERS = ("{{", "formulaText")


class ClayError(ValueError):
    """Raised when a Clay table schema can't be imported."""


def slugify(name: str) -> str:
    s = SLUG_RE.sub("_", name.strip().lower()).strip("_")
    return s or "column"


def _slug_unique(name: str, used: set[str]) -> str:
    base = slugify(name)
    slug = base
    i = 1
    while slug in used:
        slug = f"{base}_{i}"
        i += 1
    used.add(slug)
    return slug


def _is_computed(field: dict) -> bool:
    return any(k in field for k in ("formulaText", "prompt", "url", "waterfall", "inputMapping"))


def import_table(schema: Any, name: str | None = None,
                 source_csv: str | None = None) -> dict:
    """Clay table schema -> gtmharness pipeline dict.

    schema: the object returned by Clay's clay_get_table (dict with 'fields'),
            or a bare list of field dicts.
    name:   pipeline name override ([a-z0-9_]); default slugs the table name.
    source_csv: path to the clay_export_table CSV this pipeline will read.
    """
    if isinstance(schema, list):
        fields = schema
        table_name = "clay_table"
    else:
        if not isinstance(schema, dict):
            raise ClayError("clay schema must be a JSON object (clay_get_table output) or a field list")
        fields = schema.get("fields")
        if fields is None:
            raise ClayError("clay schema missing 'fields' (is this a clay_get_table export?)")
        table_name = str(schema.get("name") or "clay_table")
    if not fields:
        raise ClayError("clay table has no fields")

    if name is not None:
        # Explicit name: take it literally, don't silently repair it.
        if not re.fullmatch(r"[a-z0-9_]+", name):
            raise ClayError(f"pipeline name '{name}' is not [a-z0-9_] — "
                            "slugs must be lowercase letters, digits, underscores")
        pipe_name = name
    else:
        pipe_name = slugify(table_name)

    used: set[str] = set()
    contract: list[dict] = []
    field_map: dict[str, str] = {}
    computed: dict[str, dict] = {}
    for f in fields:
        if not isinstance(f, dict) or not f.get("name"):
            raise ClayError(f"clay field must be an object with a 'name': {f!r}")
        slug = _slug_unique(f["name"], used)
        field_map[str(f.get("id", f["name"]))] = slug
        ctype = str(f.get("type", "text")).lower()
        if ctype not in TYPE_MAP:
            raise ClayError(f"field '{f['name']}': unknown Clay type '{ctype}'")
        contract.append({
            "name": slug,
            "type": TYPE_MAP[ctype],
            "required": not _is_computed(f),
        })
        if _is_computed(f):
            extra = {k: v for k, v in f.items()
                     if k in {"formulaText", "prompt", "url", "waterfall", "inputMapping", "model", "outputFields"}}
            if extra:
                computed[slug] = extra

    src_config: dict[str, Any] = {
        "field_map": field_map,
        # Clay CSV exports type every cell as text; the adapter coerces these
        # so the contract's number/boolean/datetime fields plan cleanly.
        "types": {f["name"]: f["type"] for f in contract},
    }
    if source_csv:
        src_config["path"] = source_csv
    if computed:
        src_config["computed_columns"] = computed

    return {
        "name": pipe_name,
        "steps": [
            {"name": "clay_table", "kind": "source", "using": "clay_csv", "config": src_config},
            {"name": "sink", "kind": "sink", "using": "dry", "contract": contract},
        ],
    }


def import_file(path: str, name: str | None = None, source_csv: str | None = None) -> dict:
    import json
    from pathlib import Path

    raw = Path(path).read_text()
    try:
        schema = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ClayError(f"{path} is not valid JSON: {e}") from e
    return import_table(schema, name=name, source_csv=source_csv)
