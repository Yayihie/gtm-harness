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
    raise ValueError(f"unsupported source adapter '{using}' (built-ins: csv, json)")
