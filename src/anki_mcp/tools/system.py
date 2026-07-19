"""Connectivity and sync tools."""

from __future__ import annotations

from fastmcp import FastMCP

from ..client import AnkiConnectClient
from ..errors import handle_api_error
from ..formatting import ResponseFormat, to_json
from ._common import READ_ONLY, WRITE


def register(mcp: FastMCP, client: AnkiConnectClient) -> None:
    """Register the system tools on `mcp`, closing over `client`."""

    @mcp.tool(annotations=READ_ONLY)
    async def anki_check_connection(
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Check that Anki is running and AnkiConnect is reachable.

        Call this first when any other Anki tool fails — it distinguishes "Anki
        is closed" from "the request itself was wrong".

        Returns the AnkiConnect API version (6) on success.
        """
        try:
            version = await client.invoke("version")
        except Exception as exc:
            return handle_api_error(exc)

        if response_format == ResponseFormat.JSON:
            return to_json({"connected": True, "version": version, "url": client.url})

        return (
            f"Connected to AnkiConnect at {client.url} (API version {version}). "
            "Anki is running."
        )

    @mcp.tool(annotations=WRITE)
    async def anki_sync(
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Sync the local collection with AnkiWeb.

        Requires AnkiWeb credentials already configured in Anki — this cannot log
        in for you. The action returns nothing on success; a sync conflict opens
        a modal dialog *in Anki*, which blocks AnkiConnect until you resolve it
        (the call will then time out).
        """
        try:
            await client.invoke("sync")
        except Exception as exc:
            return handle_api_error(exc)

        if response_format == ResponseFormat.JSON:
            return to_json({"synced": True})

        return "Sync with AnkiWeb triggered successfully."
