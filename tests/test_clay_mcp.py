"""Clay MCP wiring: gtm-harness speaks the MCP stdio JSON-RPC protocol to the
clay-mcp-public server. Verified against a fixture server speaking the same
protocol (initialize -> notifications/initialized -> tools/call), so the
round-trip is real without needing node/Clay access."""
import json
import os
import sys

import pytest
import yaml

from gtmharness.clay_mcp import ClayMcpClient, ClayMcpError, import_from_mcp
from gtmharness.cli import load_pipeline_str

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "fake_clay_mcp.py")
SCHEMA = os.path.join(os.path.dirname(__file__), "..", "examples", "clay_companies.json")


def _argv() -> list[str]:
    return [sys.executable, FIXTURE, SCHEMA]


def test_initialize_and_call_tool():
    client = ClayMcpClient(_argv())
    try:
        info = client.initialize()
        assert info["serverInfo"]["name"] == "fake-clay-mcp"
        schema = client.call_tool("clay_get_table", {"tableId": "t_abc123xyz"})
        assert schema["name"] == "AI Startups Pipeline"
        assert len(schema["fields"]) == 8
    finally:
        client.close()


def test_import_from_mcp_produces_valid_spec():
    p = import_from_mcp("t_abc123xyz", _argv(), name="ai_startups")
    pipeline = load_pipeline_str(yaml.safe_dump(p, sort_keys=False))
    assert pipeline.name == "ai_startups"
    assert [f.name for f in pipeline.sinks()[0].contract][0] == "email"


def test_import_from_mcp_with_export_downloads_csv(tmp_path):
    out_csv = tmp_path / "t.csv"
    p = import_from_mcp("t_abc123xyz", _argv(), name="ai_startups",
                        view_id="gv_1", out_csv=str(out_csv))
    # the fixture's file:// URL points at the real example CSV
    rows_csv = open(out_csv).read()
    assert "jane@acmeai.com" in rows_csv
    src = p["steps"][0]
    assert src["config"]["path"] == str(out_csv)
    pipeline = load_pipeline_str(yaml.safe_dump(p, sort_keys=False))
    assert pipeline.name == "ai_startups"


def test_unknown_tool_raises():
    client = ClayMcpClient(_argv())
    try:
        client.initialize()
        with pytest.raises(ClayMcpError):
            client.call_tool("clay_not_a_tool", {})
    finally:
        client.close()


def test_missing_server_binary_raises():
    with pytest.raises(ClayMcpError):
        ClayMcpClient(["/nonexistent/mcp-server-bin"]).initialize()


def test_cli_import_clay_mcp(tmp_path):
    """CLI: --table-id --mcp-path goes live through the MCP server."""
    from gtmharness.cli import main
    out = tmp_path / "clay.yaml"
    rc = main(["import-clay", "--table-id", "t_abc123xyz", "--mcp-path",
               f"{sys.executable} {FIXTURE} {SCHEMA}",
               "--name", "ai_startups", "-o", str(out)])
    assert rc == 0
    text = out.read_text()
    assert "name: ai_startups" in text
    assert "clay_csv" in text  # source adapter is wired


def test_session_cookie_passed_via_env():
    """The client forwards CLAY_SESSION_COOKIE to the server process env,
    proven end-to-end through a fixture tool that echoes its own env."""
    client = ClayMcpClient(_argv(), session_cookie="s%3Atest-cookie")
    try:
        client.initialize()
        echoed = client.call_tool("test_echo_env", {})
        assert echoed["clay_session_cookie"] == "s%3Atest-cookie"
    finally:
        client.close()
