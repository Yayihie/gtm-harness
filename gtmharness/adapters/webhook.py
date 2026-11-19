"""Webhook sink adapter — POST rows to an HTTP endpoint.

Still gated by the dry-run plan + audit log; this is only the final "do it" step.
"""

from __future__ import annotations

import json
import urllib.request


def write_rows(config: dict, rows: list[dict]) -> list[dict]:
    url = config.get("url")
    if not url:
        raise RuntimeError("webhook sink config needs a 'url'")
    headers = {"Content-Type": "application/json"}
    if config.get("secret"):
        headers["Authorization"] = f"Bearer {config['secret']}"
    out = []
    for row in rows:
        try:
            req = urllib.request.Request(url, data=json.dumps(row).encode(), headers=headers)
            with urllib.request.urlopen(req, timeout=30) as r:
                out.append({"key": row.get("email"), "id": None, "status": f"posted {r.status}"})
        except Exception as e:
            out.append({"key": row.get("email"), "id": None, "status": f"error: {e}"})
    return out
