"""Adapters package: optional provider integrations + a plugin registry.

Core gtm-harness has zero hard deps. CRM/enrichment adapters import their SDK
lazily and raise a helpful error if the SDK is not installed:

    pip install gtmharness[hubspot]
    pip install gtmharness[salesforce]

Plugin registry — custom sinks can be registered programmatically:

    from gtmharness.adapters import register

    register("my_sink", lambda config, rows: [{"key": r["email"], "id": None,
                                               "status": "posted"} for r in rows])

Then use `using: my_sink` in a pipeline spec (and add it to spec.VALID_SINKS
when registering programmatically, e.g. in tests or a sitecustomize hook).
"""

from typing import Callable

REGISTRY: dict[str, Callable] = {}


def register(name: str, fn: Callable) -> None:
    """Register a sink adapter under `name`; fn(config, rows) -> list[dict]."""
    REGISTRY[name] = fn
