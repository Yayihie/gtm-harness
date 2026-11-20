"""Minimal MCP stdio client for the Clay MCP server (shanefirek/clay-mcp-public).

Clay has no public API; the MCP server maps Clay's internal surface and runs as
a stdio MCP server (`node dist/index.js` with CLAY_SESSION_COOKIE in env).
This client speaks the MCP JSON-RPC protocol over stdin/stdout: initialize
handshake, then tools/call. It pulls a table's schema (clay_get_table) and its
rows (clay_export_table -> download URL) so `import-clay --mcp` can go
table-id -> pipeline YAML without a hand-exported JSON file.

The client is server-agnostic: it takes an argv list, so tests drive it against
a Python fixture speaking the same protocol instead of needing node/Clay.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

JSONRPC = "2.0"


class ClayMcpError(RuntimeError):
    """Raised when the Clay MCP server is unreachable or a tool call fails."""


class ClayMcpClient:
    def __init__(self, argv: list[str], session_cookie: str | None = None,
                 timeout_s: float = 60.0):
        if not argv:
            raise ClayMcpError("MCP server argv is empty")
        self.argv = argv
        self.session_cookie = session_cookie
        self.timeout_s = timeout_s
        self._next_id = 0
        self._proc = None

    # -- protocol ----------------------------------------------------------

    def _start(self) -> None:
        env = dict(os.environ)
        if self.session_cookie:
            env["CLAY_SESSION_COOKIE"] = self.session_cookie
        try:
            self._proc = subprocess.Popen(
                self.argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=env, text=True)
        except FileNotFoundError as e:
            raise ClayMcpError(f"cannot start MCP server {self.argv}: {e}") from e

    def _send(self, msg: dict) -> None:
        assert self._proc is not None and self._proc.stdin
        self._proc.stdin.write(json.dumps(msg) + "\n")
        self._proc.stdin.flush()

    def _read_msg(self) -> dict:
        assert self._proc is not None and self._proc.stdout
        line = self._proc.stdout.readline()
        if not line:
            err = self._proc.stderr.read() if self._proc.stderr else ""
            raise ClayMcpError(f"MCP server closed stdout. stderr: {err.strip()[:500]}")
        try:
            return json.loads(line)
        except json.JSONDecodeError as e:
            raise ClayMcpError(f"MCP server sent non-JSON line: {line.strip()[:200]}") from e

    def _request(self, method: str, params: dict) -> dict:
        self._next_id += 1
        msg = {"jsonrpc": JSONRPC, "id": self._next_id, "method": method, "params": params}
        self._send(msg)
        # Skip notifications (no id) until the response for our id arrives.
        while True:
            resp = self._read_msg()
            if resp.get("id") == self._next_id:
                break
        if "error" in resp:
            raise ClayMcpError(f"MCP {method} failed: {resp['error']}")
        return resp.get("result", {})

    # -- public ------------------------------------------------------------

    def initialize(self) -> dict:
        self._start()
        result = self._request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "gtmharness", "version": "0.5.0"},
        })
        # MCP: client must confirm initialization before calling tools.
        self._send({"jsonrpc": JSONRPC, "method": "notifications/initialized"})
        return result

    def call_tool(self, name: str, arguments: dict) -> Any:
        result = self._request("tools/call", {"name": name, "arguments": arguments})
        if result.get("isError"):
            text = _content_text(result)
            raise ClayMcpError(f"clay tool '{name}' returned an error: {text[:500]}")
        text = _content_text(result)
        if not text:
            raise ClayMcpError(f"clay tool '{name}' returned no content")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text  # some tools return plain text (e.g. a download URL)

    def close(self) -> None:
        if self._proc is not None:
            try:
                self._proc.stdin.close()  # type: ignore[union-attr]
            except BrokenPipeError:
                pass
            self._proc.wait(timeout=5)
            self._proc = None


def _content_text(result: dict) -> str:
    parts = result.get("content") or []
    return "".join(p.get("text", "") for p in parts if isinstance(p, dict))


def export_table_to_csv(client: ClayMcpClient, table_id: str, view_id: str,
                        out_csv: str) -> str:
    """clay_export_table -> download URL -> local CSV file. Returns the path."""
    result = client.call_tool("clay_export_table", {"tableId": table_id, "viewId": view_id})
    url = _extract_download_url(result)
    if not url:
        raise ClayMcpError(f"clay_export_table returned no download URL: {result!r:.300}")
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            data = resp.read()
    except OSError as e:
        raise ClayMcpError(f"downloading exported CSV failed: {e}") from e
    with open(out_csv, "wb") as f:
        f.write(data)
    return out_csv


def _extract_download_url(result: Any) -> str | None:
    def _is_url(v: object) -> bool:
        return isinstance(v, str) and "://" in v

    if isinstance(result, str):
        return result if _is_url(result) else None
    if not isinstance(result, dict):
        return None
    for key in ("downloadUrl", "url", "download_url"):
        v = result.get(key)
        if _is_url(v):
            return v
    # Poll-style job objects carry the URL under data/job/data.
    for nested in ("data", "job", "export"):
        inner = result.get(nested)
        if isinstance(inner, dict):
            found = _extract_download_url(inner)
            if found:
                return found
    return None


def import_from_mcp(table_id: str, server_argv: list[str], session_cookie: str | None = None,
                    name: str | None = None, view_id: str | None = None,
                    out_csv: str | None = None) -> dict:
    """Live Clay table -> pipeline dict. Fetches schema via MCP, optionally the CSV."""
    from .clay import import_table
    client = ClayMcpClient(server_argv, session_cookie=session_cookie)
    try:
        client.initialize()
        schema = client.call_tool("clay_get_table", {"tableId": table_id})
        csv_path = None
        if view_id:
            csv_path = export_table_to_csv(client, table_id, view_id, out_csv or f"{table_id}.csv")
    finally:
        client.close()
    return import_table(schema, name=name, source_csv=csv_path)
