"""Start the installed `esgo-mcp` command as an AI app would (stdio) and check it.

    python .github/scripts/smoke_stdio.py <path-to-esgo-mcp>

Lists the tools and calls `me_retrieve` against the real API with an invalid
key. Expected: one tool per API operation and an API error (401 or 503), never
a crash. Exits non-zero otherwise.
"""

import sys

import anyio
from mcp import Client, StdioServerParameters

EXPECTED = {"me_retrieve", "matches_search", "open_requests_create", "open_requests_list_matches"}


async def main(command: str) -> None:
    params = StdioServerParameters(command=command, args=[], env={"ESGO_API_KEY": "esgo_live_smoke_invalid"})
    async with Client(params) as client:
        tools = {tool.name for tool in (await client.list_tools()).tools}
        missing = EXPECTED - tools
        if missing:
            raise SystemExit(f"missing tools: {sorted(missing)}")
        result = await client.call_tool("me_retrieve", {})
        text = result.content[0].text
        if not result.is_error or not ("[401]" in text or "[503]" in text):
            raise SystemExit(f"unexpected result: {text}")
    print(f"ok: {len(tools)} tools, me_retrieve -> {text}")


if __name__ == "__main__":
    anyio.run(main, sys.argv[1])
