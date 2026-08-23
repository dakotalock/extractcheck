#!/usr/bin/env python3
"""Minimal stdio JSON-RPC MCP server exposing check_extract."""
from __future__ import annotations

import json
import sys
from typing import Any

from extractcheck import __version__
from extractcheck.service import run_check

TOOL = {
    "name": "check_extract",
    "description": (
        "Refetch a public URL, extract independently, and verify a claimed JSON extract. "
        "Returns pass/fail, diffs, and a signed receipt. No charge if fetch fails or body is empty."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Public http(s) page to verify"},
            "claim": {"type": "object", "description": "Claimed extract fields to check"},
            "schema": {"type": "object", "description": "Optional JSON Schema for the claim"},
        },
        "required": ["url", "claim"],
    },
}


def _ok(id_: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def _err(id_: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def handle(msg: dict[str, Any]) -> dict[str, Any] | None:
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}
    if method == "initialize":
        return _ok(
            mid,
            {
                "protocolVersion": params.get("protocolVersion") or "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "extractcheck", "version": __version__},
            },
        )
    if method == "notifications/initialized":
        return None
    if method in {"tools/list", "list_tools"}:
        return _ok(mid, {"tools": [TOOL]})
    if method in {"tools/call", "call_tool"}:
        name = params.get("name")
        args = params.get("arguments") or params.get("args") or {}
        if name != "check_extract":
            return _err(mid, -32601, f"unknown tool: {name}")
        url = args.get("url")
        claim = args.get("claim")
        if not url or not isinstance(claim, dict):
            return _err(mid, -32602, "url and claim object are required")
        result = run_check(url, claim, args.get("schema"))
        return _ok(
            mid,
            {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                "structuredContent": result,
                "isError": False,
            },
        )
    if method == "ping":
        return _ok(mid, {})
    if mid is None:
        return None
    return _err(mid, -32601, f"unknown method: {method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(json.dumps(_err(None, -32700, "parse error")) + "\n")
            sys.stdout.flush()
            continue
        reply = handle(msg)
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
