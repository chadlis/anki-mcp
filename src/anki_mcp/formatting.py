"""Output formatting shared by all tools.

Tools return **text**, not objects: an MCP client reads their result as a
string. Markdown is the default because it is compact and readable in a chat
transcript; `response_format="json"` gives the exact payload when the caller
needs to parse it or pass ids to another tool.
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Any


class ResponseFormat(StrEnum):
    """How a tool should render its result.

    A `StrEnum` so the members compare equal to the plain strings a client
    sends over the wire (`"markdown"`, `"json"`).
    """

    MARKDOWN = "markdown"
    JSON = "json"


def to_json(data: Any) -> str:
    """Serialize `data` as indented JSON.

    `ensure_ascii=False` matters here: Anki decks and notes are routinely
    non-Latin (Arabic, Japanese, accented French), and escaping them to `\\uXXXX`
    would make the output unreadable.
    """
    return json.dumps(data, indent=2, ensure_ascii=False)


def heading(title: str, count: int | None = None) -> str:
    """Render a section heading, optionally with an item count."""
    return f"## {title}" if count is None else f"## {title} ({count})"


def bullet_list(title: str, items: list[str]) -> str:
    """Render a titled bullet list, or a friendly note when there is nothing."""
    if not items:
        return f"{heading(title, 0)}\n\n_None found._"
    lines = "\n".join(f"- {item}" for item in items)
    return f"{heading(title, len(items))}\n\n{lines}"


def truncate(text: str, limit: int = 120) -> str:
    """Shorten `text` to `limit` characters for display in a summary line.

    Note fields hold full HTML documents; dumping them whole into a listing is
    unreadable, so previews get clipped.
    """
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1] + "…"
