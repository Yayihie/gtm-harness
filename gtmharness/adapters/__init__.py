"""Adapters package: optional provider integrations.

Core gtm-harness has zero hard deps. CRM/enrichment adapters import their SDK
lazily and raise a helpful error if the SDK is not installed:

    pip install gtmharness[hubspot]
    pip install gtmharness[salesforce]
"""
