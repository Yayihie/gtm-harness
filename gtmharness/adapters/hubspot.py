"""HubSpot sink adapter — wraps the official HubSpot Python SDK (optional extra).

Writes contacts/leads through the SDK's CRM API. Every write still goes through
the harness dry-run plan + audit log; this adapter is only the final "do it" step.
"""

from __future__ import annotations


def _client(config: dict):
    token = config.get("token")
    if not token:
        raise RuntimeError("HubSpot sink config needs a 'token' (private app access token)")
    try:
        from hubspot import HubSpot  # official hubspot-api-python  # pyright: ignore
    except ImportError as e:
        raise RuntimeError(
            "HubSpot adapter requires the official SDK: pip install 'gtmharness[hubspot]'"
        ) from e
    return HubSpot(access_token=token)


def write_rows(config: dict, rows: list[dict]) -> list[dict]:
    """Write rows as HubSpot contacts. Returns [{'key', 'id', 'status'}]."""
    client = _client(config)
    out = []
    for row in rows:
        props = {k: v for k, v in row.items() if k in config.get("property_map", row.keys())}
        props.setdefault("email", row.get("email"))
        try:
            created = client.crm.contacts.basic_api.create(
                simple_public_object_input_for_create={"properties": props}
            )
            out.append({"key": row.get("email"), "id": created.id, "status": "created"})
        except Exception as e:
            out.append({"key": row.get("email"), "id": None, "status": f"error: {e}"})
    return out
