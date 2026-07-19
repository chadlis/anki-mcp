"""Annotation dicts shared by the tool modules.

MCP tool *annotations* are hints for the client: they let Claude Desktop show a
confirmation prompt before a destructive call, or skip one for a plain read.
They are advisory — the server still has to behave correctly regardless.
"""

from __future__ import annotations

from typing import Any

# A pure read: no side effect on the collection.
READ_ONLY: dict[str, Any] = {
    "readOnlyHint": True,
    "openWorldHint": True,
}

# Writes something new, but does not destroy existing data. Anki's own duplicate
# detection makes most of these safe to retry, hence idempotentHint stays False
# only where a retry would genuinely add a second note.
WRITE: dict[str, Any] = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "openWorldHint": True,
}

# Modifies data that already exists — overwriting a field loses its old content.
DESTRUCTIVE: dict[str, Any] = {
    "readOnlyHint": False,
    "destructiveHint": True,
    "openWorldHint": True,
}
