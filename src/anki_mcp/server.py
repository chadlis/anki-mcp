"""Server construction and entry point.

Shape of an MCP server, in three steps:

1. Build a `FastMCP` instance — the registry that will hold the tools.
2. Register tools on it. Each becomes a callable the MCP client can discover,
   with its schema derived from the Python signature and its description from
   the docstring. **The docstrings are the API**: they are what the model reads
   to decide which tool to call and with what arguments.
3. Run it over a transport. `stdio` (the default) means the client launches this
   process and speaks JSON-RPC over its stdin/stdout — which is why nothing here
   may ever `print()` to stdout: that would corrupt the protocol stream.
"""

from __future__ import annotations

from fastmcp import FastMCP

# Absolute imports on purpose: `fastmcp inspect src/anki_mcp/server.py:mcp`
# loads this file as a standalone module, where relative imports have no parent
# package. The rest of the package uses relative imports normally.
from anki_mcp.client import AnkiConnectClient
from anki_mcp.config import Settings
from anki_mcp.tools import register_all

INSTRUCTIONS = """\
Bridges to a local Anki collection through the AnkiConnect add-on.

Anki must be running on this machine for any tool to work; anki_check_connection
tells you whether it is.

Note fields are HTML fragments and are sent to Anki verbatim — write the markup
you want rendered (<b>, <pre><code>, <span class="hljs-...">) and do not escape
it. Cloze deletions use {{c1::...}} and need a cloze note type.
"""


def build_server(settings: Settings | None = None) -> FastMCP:
    """Create the FastMCP instance with all tools registered."""
    settings = settings or Settings.from_env()
    client = AnkiConnectClient(settings)

    mcp = FastMCP(name="anki-mcp", instructions=INSTRUCTIONS)
    register_all(mcp, client)
    return mcp


# Module-level instance. This is the object a `module:object` deploy target
# points at (`src/anki_mcp/server.py:mcp`), and what `main()` runs.
mcp = build_server()


def main() -> None:
    """Console entry point for `anki-mcp`.

    Picks the transport from `MCP_TRANSPORT`: stdio by default (Claude Desktop
    launches the process itself), or streamable-http on HOST:PORT.
    """
    settings = Settings.from_env()

    if settings.transport == "http":
        mcp.run(transport="http", host=settings.host, port=settings.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
