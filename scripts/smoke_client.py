"""Manual end-to-end check against a real Anki.

Unlike the test suite, this talks to your actual collection: it starts the
server over stdio exactly as Claude Desktop does, then calls the two read-only
tools. Nothing is created or modified.

    uv run python scripts/smoke_client.py

Requires Anki to be running with the AnkiConnect add-on installed.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from fastmcp import Client

SERVER = Path(__file__).resolve().parent.parent / "src" / "anki_mcp" / "server.py"


async def main() -> int:
    # Pointing the Client at the server file makes it spawn the process and
    # speak MCP over its stdin/stdout — the same handshake a real client does.
    async with Client(str(SERVER)) as client:
        tools = await client.list_tools()
        print(f"Server exposes {len(tools)} tools:")
        for tool in sorted(tools, key=lambda t: t.name):
            summary = (tool.description or "").strip().splitlines()[0]
            print(f"  - {tool.name}: {summary}")

        print("\nanki_check_connection:")
        result = await client.call_tool("anki_check_connection")
        connection = result.content[0].text
        print(f"  {connection}")

        if connection.startswith("Error:"):
            # Anki is closed or the add-on is missing — listing decks would just
            # repeat the same error, so stop here with a non-zero exit.
            return 1

        print("\nanki_list_decks:")
        result = await client.call_tool("anki_list_decks")
        print(result.content[0].text)

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
