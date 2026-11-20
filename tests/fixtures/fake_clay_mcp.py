"""Fixture: a fake Clay MCP server speaking real MCP stdio JSON-RPC.

Serves the same protocol as shanefirek/clay-mcp-public:
initialize -> notifications/initialized -> tools/call. Used by test_clay_mcp.py
to prove the client's protocol handling without needing node or Clay access.
"""
import json
import sys

SCHEMA = {
    "name": "AI Startups Pipeline",
    "fields": [
        {"id": "f_email", "name": "Email", "type": "email"},
        {"id": "f_headcount", "name": "Headcount", "type": "number"},
    ],
}
import os

CSV_URL = "file://" + os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "examples", "clay_companies.csv"))


def main() -> int:
    schema_path = sys.argv[1] if len(sys.argv) > 1 else None
    schema = json.load(open(schema_path)) if schema_path else SCHEMA
    for line in sys.stdin:
        msg = json.loads(line)
        if "id" not in msg:
            continue  # notification
        method = msg.get("method")
        if method == "initialize":
            result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "fake-clay-mcp", "version": "1.0.0"}}
        elif method == "tools/call":
            name = msg["params"]["name"]
            if name == "clay_get_table":
                result = {"content": [{"type": "text", "text": json.dumps(schema)}]}
            elif name == "clay_export_table":
                result = {"content": [{"type": "text",
                                       "text": json.dumps({"downloadUrl": CSV_URL})}]}
            elif name == "test_echo_env":
                result = {"content": [{"type": "text",
                                       "text": json.dumps({"clay_session_cookie":
                                                           os.environ.get("CLAY_SESSION_COOKIE")})}]}
            else:
                result = {"isError": True,
                          "content": [{"type": "text", "text": f"unknown tool {name}"}]}
        else:
            result = {"isError": True, "content": [{"type": "text", "text": "bad method"}]}
        print(json.dumps({"jsonrpc": "2.0", "id": msg["id"], "result": result}), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
