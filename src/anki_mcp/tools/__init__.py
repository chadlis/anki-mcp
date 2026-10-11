"""Tool registry.

One module per domain, each exposing `register(mcp, client)`. To add a tool,
extend the relevant module (or create one and list it below).
"""

from __future__ import annotations

from fastmcp import FastMCP

from ..client import AnkiConnectClient
from . import decks, models, notes, organize, system


def register_all(mcp: FastMCP, client: AnkiConnectClient) -> None:
    """Register every tool module on the server."""
    system.register(mcp, client)
    decks.register(mcp, client)
    models.register(mcp, client)
    notes.register(mcp, client)
    organize.register(mcp, client)


__all__ = ["register_all"]
