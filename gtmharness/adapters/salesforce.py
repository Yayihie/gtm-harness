"""Salesforce sink adapter — wraps simple-salesforce (optional extra).

Writes leads through the Salesforce REST API. Harness dry-run + audit still
gate the run; this adapter is only the final "do it" step.
"""

from __future__ import annotations


def _client(config: dict):
    creds = {k: config.get(k) for k in ("username", "password", "security_token") if config.get(k)}
    if len(creds) < 3:
        raise RuntimeError("Salesforce sink config needs username, password, security_token")
    try:
        from simple_salesforce import Salesforce  # MIT-licensed simple-salesforce  # pyright: ignore
    except ImportError as e:
        raise RuntimeError(
            "Salesforce adapter requires simple-salesforce: pip install 'gtmharness[salesforce]'"
        ) from e
    return Salesforce(**creds)


def write_rows(config: dict, rows: list[dict]) -> list[dict]:
    """Write rows as Salesforce Leads. Returns [{'key', 'id', 'status'}]."""
    client = _client(config)
    out = []
    for row in rows:
        props = {k: v for k, v in row.items() if k in config.get("property_map", row.keys())}
        try:
            result = client.Lead.create(props)
            out.append({"key": row.get("email"), "id": result.get("id"),
                        "status": "created" if result.get("success") else "error"})
        except Exception as e:
            out.append({"key": row.get("email"), "id": None, "status": f"error: {e}"})
    return out
