"""The MCP server: tools/list and tools/call, both generated from the spec.

Run with `uvx esgo-mcp` (or `python -m esgo_mcp`). Configuration via environment:
  ESGO_API_KEY   your ESGO API key (esgo_live_...)
  ESGO_BASE_URL  optional, default https://api.es-go.de

stdout carries the MCP protocol, so everything else goes to stderr.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

import anyio
import httpx2
import mcp_types as types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

from . import api
from ._version import __version__
from .spec import DEFAULT_BASE_URL, Operation, load_spec, operations

logger = logging.getLogger("esgo_mcp")

INSTRUCTIONS = (
    "Tools for the ESGO API. ESGO is a marketplace that matches empty truck runs of carriers "
    "with freight of shippers (road freight, Germany and Europe). Weights are in kilograms; "
    "times without a time zone are local time Europe/Berlin. Prices in search results are "
    "non-binding estimates; ESGO is a broker, not a carrier. Bookings happen on es-go.de via the "
    "booking_url of a match. Tools that create data (e.g. open requests) count against daily "
    "quotas of the API key; confirm with the user before calling them."
)


def create_server(spec: dict[str, Any], *, api_key: str | None, base_url: str,
                  http: httpx2.AsyncClient) -> Server:
    ops: dict[str, Operation] = {op.name: op for op in operations(spec)}

    async def list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=[_tool(op) for op in ops.values()])

    async def call_tool(ctx, params: types.CallToolRequestParams) -> types.CallToolResult:
        op = ops.get(params.name)
        if op is None:
            return _error(f"Unknown tool: {params.name}")
        outcome = await api.call(op, params.arguments, api_key=api_key, base_url=base_url, http=http)
        if not outcome.ok:
            return _error(outcome.message)
        text = json.dumps(outcome.data, ensure_ascii=False, indent=2)
        return types.CallToolResult(
            content=[types.TextContent(text=text)],
            structured_content=outcome.data if isinstance(outcome.data, dict) else None,
        )

    return Server(
        "esgo",
        version=__version__,
        title="ESGO",
        instructions=INSTRUCTIONS,
        website_url="https://es-go.de/developers",
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def _tool(op: Operation) -> types.Tool:
    return types.Tool(
        name=op.name,
        title=op.title,
        description=op.description,
        input_schema=op.input_schema,
        annotations=types.ToolAnnotations(
            title=op.title,
            read_only_hint=op.read_only,
            # Creating something is not destructive; deleting or overwriting is.
            destructive_hint=op.method in ("DELETE", "PUT", "PATCH"),
            idempotent_hint=op.read_only,
            open_world_hint=True,        # talks to an external service
        ),
    )


def _error(message: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(text=message)], is_error=True)


async def _serve(api_key: str | None, base_url: str) -> None:
    spec, source = load_spec(base_url)
    logger.info("esgo-mcp %s: %d tools from the %s spec (%s)",
                __version__, len(operations(spec)), source, base_url)
    if not api_key:
        logger.warning("ESGO_API_KEY is not set; tools are listed, but every call will fail.")
    async with httpx2.AsyncClient(timeout=30.0) as http:
        server = create_server(spec, api_key=api_key, base_url=base_url, http=http)
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx2").setLevel(logging.WARNING)  # one line per request is noise in the AI app's log
    api_key = os.environ.get("ESGO_API_KEY") or None
    base_url = (os.environ.get("ESGO_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
    anyio.run(_serve, api_key, base_url)
