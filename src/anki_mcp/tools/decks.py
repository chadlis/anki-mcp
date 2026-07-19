"""Deck tools."""

from __future__ import annotations

from fastmcp import FastMCP

from ..client import AnkiConnectClient
from ..errors import handle_api_error
from ..formatting import ResponseFormat, bullet_list, to_json
from ._common import READ_ONLY, WRITE


def register(mcp: FastMCP, client: AnkiConnectClient) -> None:
    """Register the deck tools on `mcp`, closing over `client`."""

    @mcp.tool(annotations=READ_ONLY)
    async def anki_list_decks(
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List every deck in the collection.

        Nested decks are returned with `::` as the separator, e.g.
        `"Python::Asyncio"` is the "Asyncio" subdeck of "Python".
        """
        try:
            decks = await client.invoke("deckNames")
        except Exception as exc:
            return handle_api_error(exc)

        if response_format == ResponseFormat.JSON:
            return to_json(decks)

        return bullet_list("Decks", sorted(decks))

    @mcp.tool(annotations=WRITE)
    async def anki_create_deck(
        deck: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Create a deck, if it does not already exist.

        Args:
            deck: Deck name. Use `::` to nest, e.g. `"Python::Asyncio"` — every
                missing parent in the path is created too. Creating a deck that
                already exists is a no-op, not an error.

        Returns the deck id.
        """
        try:
            deck_id = await client.invoke("createDeck", deck=deck)
        except Exception as exc:
            return handle_api_error(exc)

        if response_format == ResponseFormat.JSON:
            return to_json({"deck": deck, "id": deck_id})

        return f"Deck {deck!r} is ready (id {deck_id})."
