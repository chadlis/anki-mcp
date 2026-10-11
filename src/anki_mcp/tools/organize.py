"""Organization tools: tag notes, suspend cards.

Two levels, easy to confuse:

- **Tags live on notes.** `anki_add_tags` / `anki_remove_tags` take note ids
  (from `anki_find_notes`).
- **Suspension lives on cards.** A note can generate several cards (cloze
  c1/c2, reversed pairs), and each is suspended on its own. `anki_suspend`
  therefore takes a *search query* and resolves it to card ids itself, so every
  card of the matching notes is covered.
"""

from __future__ import annotations

from fastmcp import FastMCP

from ..client import AnkiConnectClient
from ..errors import handle_api_error
from ..formatting import ResponseFormat, to_json
from ._common import WRITE


def _check_tags(tags: list[str]) -> str | None:
    """Return an error message if a tag is unusable, else None.

    AnkiConnect takes tags as ONE space-separated string, so a tag containing a
    space would silently turn into two tags.
    """
    if not tags:
        return "Error: no tags given."
    bad = [tag for tag in tags if not tag or any(ch.isspace() for ch in tag)]
    if bad:
        return f"Error: tags cannot be empty or contain spaces: {bad!r}. Use `::` to nest."
    return None


def register(mcp: FastMCP, client: AnkiConnectClient) -> None:
    """Register the organization tools on `mcp`, closing over `client`."""

    @mcp.tool(annotations=WRITE)
    async def anki_add_tags(
        notes: list[int],
        tags: list[str],
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Add tags to notes. Existing tags are kept; re-adding a tag is a no-op.

        Args:
            notes: Note ids, from `anki_find_notes`.
            tags: Tags to add, e.g. `["attend::M2"]`. No spaces; `::` nests.
        """
        if error := _check_tags(tags):
            return error
        try:
            await client.invoke("addTags", notes=notes, tags=" ".join(tags))
        except Exception as exc:
            return handle_api_error(exc)

        if response_format == ResponseFormat.JSON:
            return to_json({"notes": notes, "added": tags})
        return f"Added {', '.join(tags)} to {len(notes)} note(s)."

    @mcp.tool(annotations=WRITE)
    async def anki_remove_tags(
        notes: list[int],
        tags: list[str],
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Remove tags from notes. Notes that lack the tag are left unchanged.

        Only the exact tag is removed: removing `focus` leaves `focus::3fils`.

        Args:
            notes: Note ids, from `anki_find_notes` (e.g. query `tag:focus::3fils`).
            tags: Tags to remove.
        """
        if error := _check_tags(tags):
            return error
        try:
            await client.invoke("removeTags", notes=notes, tags=" ".join(tags))
        except Exception as exc:
            return handle_api_error(exc)

        if response_format == ResponseFormat.JSON:
            return to_json({"notes": notes, "removed": tags})
        return f"Removed {', '.join(tags)} from {len(notes)} note(s)."

    @mcp.tool(annotations=WRITE)
    async def anki_suspend(
        query: str,
        suspend: bool = True,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Suspend (or unsuspend) every card matching an Anki search query.

        Suspended cards leave the review queue until unsuspended; their
        scheduling history is kept. Reversible: call again with `suspend=False`.

        The query is resolved to **card** ids, so all cards of a multi-card note
        are covered. Typical queries:

            nid:1789466539268,1789466539270     specific notes
            tag:attend::M4                      everything with a tag
            tag:attend::M4 is:suspended         (with suspend=False) resume them

        Args:
            query: Anki search expression, same syntax as `anki_find_notes`.
            suspend: True to suspend, False to unsuspend.
        """
        try:
            cards = await client.invoke("findCards", query=query)
            if not cards:
                return f"No cards match {query!r}; nothing changed."
            action = "suspend" if suspend else "unsuspend"
            await client.invoke(action, cards=cards)
        except Exception as exc:
            return handle_api_error(exc)

        verb = "Suspended" if suspend else "Unsuspended"
        if response_format == ResponseFormat.JSON:
            return to_json({"query": query, "suspended": suspend, "cards": cards})
        return (
            f"{verb} {len(cards)} card(s) matching `{query}` "
            "(cards already in that state are counted but unchanged)."
        )
