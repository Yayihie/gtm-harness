"""Source adapters: load rows from CSV / JSON files (local, zero-credit).

Remote adapters (CRM, enrichment APIs) plug in here later; the harness core
never talks to a paid API by itself. You bring your own provider keys.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def load_rows(using: str, config: dict) -> list[dict]:
    if using == "csv":
        path = Path(config["path"])
        with open(path, newline="") as f:
            return list(csv.DictReader(f))
    if using == "json":
        return json.loads(Path(config["path"]).read_text())
    if using == "clay_csv":
        return _load_clay_csv(config)
    if using == "clay_json":
        return _load_clay_json(config)
    raise ValueError(
        f"unsupported source adapter '{using}' (built-ins: csv, json, clay_csv, clay_json)")


def _slugify(name: str) -> str:
    from .clay import slugify
    return slugify(name)


def _load_clay_csv(config: dict) -> list[dict]:
    """Rows from a clay_export_table CSV. Headers are slugified to match the
    contract; field_map additionally renames f_xxx-style headers if Clay exports
    raw field ids."""
    path = Path(config["path"])
    field_map = config.get("field_map") or {}
    types = config.get("types") or {}
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    out = []
    for row in rows:
        new = {}
        for k, v in row.items():
            if k is None:
                continue
            key = field_map.get(k, k)
            slug = _slugify(str(key))
            new[slug] = _coerce(v, types.get(slug))
        out.append(new)
    return out


def _coerce(value, type_):
    """Clay CSVs are all-text; coerce to the contract type where possible.
    Uncoercible values are left as-is so the plan gate reports them."""
    if value is None:
        return value
    if type_ == "number":
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value
    if type_ == "boolean":
        if str(value).strip().lower() in ("true", "yes", "1", "t"):
            return True
        if str(value).strip().lower() in ("false", "no", "0", "f"):
            return False
        return value
    if type_ == "datetime":
        return str(value).strip()
    return value


def _load_clay_json(config: dict) -> list[dict]:
    """Rows from a records JSON export where each record is fieldId -> value
    (the clay_mcp record format). field_map turns f_xxx ids into column names."""
    data = json.loads(Path(config["path"]).read_text())
    field_map = config.get("field_map") or {}
    records = data.get("records", data) if isinstance(data, dict) else data
    if not isinstance(records, list):
        raise ValueError("clay_json source expects a list of records")
    out = []
    for rec in records:
        if isinstance(rec, dict) and "data" in rec and isinstance(rec["data"], dict):
            rec = rec["data"]
        new = {}
        for k, v in (rec or {}).items():
            key = field_map.get(str(k), k)
            new[_slugify(str(key))] = v
        out.append(new)
    return out
