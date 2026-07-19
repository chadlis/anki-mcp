"""Note tools: create, search, inspect, update.

## Fields are HTML — and are never escaped here

An Anki field does not hold plain text, it holds an HTML fragment. Anki's editor
stores `<b>bold</b>`, `<br>`, `<div>`, syntax-highlighted `<span class="hljs-…">`
blocks, and so on. Everything in this module therefore passes field values
**through verbatim**: no escaping, no sanitizing, no whitespace normalization.

Sending `"<b>x</b>"` produces a bold *x* on the card, not the literal text
`<b>x</b>`. To show a literal angle bracket, the caller must send `&lt;` itself.
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..client import AnkiConnectClient
from ..errors import handle_api_error
from ..formatting import ResponseFormat, heading, to_json, truncate
from ._common import DESTRUCTIVE, READ_ONLY, WRITE


def _build_note(
    deck_name: str,
    model_name: str,
    fields: dict[str, str],
    tags: list[str] | None,
    allow_duplicate: bool,
) -> dict[str, Any]:
    """Assemble the `note` object AnkiConnect expects.

    Note the camelCase keys: this is AnkiConnect's wire vocabulary, translated
    here from the snake_case the tools expose.
    """
    return {
        "deckName": deck_name,
        "modelName": model_name,
        # Passed through untouched — see this module's docstring on HTML.
        "fields": fields,
        "tags": tags or [],
        "options": {
            # Anki refuses a note whose first field duplicates an existing one,
            # unless explicitly told otherwise.
            "allowDuplicate": allow_duplicate,
            "duplicateScope": "deck",
        },
    }


def register(mcp: FastMCP, client: AnkiConnectClient) -> None:
    """Register the note tools on `mcp`, closing over `client`."""

    @mcp.tool(annotations=WRITE)
    async def anki_add_note(
        deck_name: str,
        model_name: str,
        fields: dict[str, str],
        tags: list[str] | None = None,
        allow_duplicate: bool = False,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        r"""Add a single note to a deck.

        **Field values are HTML and are sent verbatim — do not escape them.**
        Write the markup you want rendered on the card:

            fields={
                "Text": 'The GIL is released during <b>I/O</b>, so '
                        '{{c1::threads}} still help for network-bound work.',
                "Back Extra": '<pre><code>'
                              '<span class="hljs-keyword">async def</span> '
                              '<span class="hljs-title">main</span>(): ...'
                              '</code></pre>',
            }

        Cloze deletions use `{{c1::hidden text}}` and require the `"Cloze"` model
        (or another cloze-type note type) — the syntax is inert on `"Basic"`.

        Args:
            deck_name: Target deck. It must already exist; create it first with
                `anki_create_deck`.
            model_name: Note type, e.g. `"Basic"` or `"Cloze"`. Its field names
                must match `fields` exactly — check with `anki_get_model_fields`.
            fields: Field name -> HTML content. Omitted fields are left empty.
            tags: Tags to attach. Anki tags cannot contain spaces; use `::` to
                nest, e.g. `"python::asyncio"`.
            allow_duplicate: By default Anki refuses a note whose first field
                already exists in the deck. Set True to add it anyway.

        Returns the new note id. Fails with a "duplicate" error rather than
        silently skipping — use `anki_add_notes` to add many and tolerate
        duplicates.
        """
        note = _build_note(deck_name, model_name, fields, tags, allow_duplicate)
        try:
            note_id = await client.invoke("addNote", note=note)
        except Exception as exc:
            return handle_api_error(exc)

        if response_format == ResponseFormat.JSON:
            return to_json({"noteId": note_id, "deckName": deck_name})

        return f"Added note {note_id} to deck {deck_name!r}."

    @mcp.tool(annotations=WRITE)
    async def anki_add_notes(
        deck_name: str,
        model_name: str,
        notes: list[dict[str, Any]],
        tags: list[str] | None = None,
        allow_duplicate: bool = False,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Add several notes at once, sharing one deck and note type.

        **Field values are HTML and are sent verbatim — do not escape them.**
        See `anki_add_note` for the field/cloze conventions; they apply per item.

        Args:
            deck_name: Target deck for every note in the batch.
            model_name: Note type for every note in the batch.
            notes: One entry per note, each a dict with:
                - `"fields"` (required): field name -> HTML content.
                - `"tags"` (optional): tags for this note, replacing `tags`.
            tags: Default tags, applied to every note that has no own `"tags"`.
            allow_duplicate: Allow notes whose first field already exists.

        Unlike `anki_add_note`, a rejected note does **not** fail the batch:
        AnkiConnect returns `null` in its place (almost always a duplicate, or a
        field name that does not exist on the model). The summary reports which
        entries were skipped, by index.
        """
        payload = [
            _build_note(
                deck_name,
                model_name,
                entry.get("fields", {}),
                entry.get("tags", tags),
                allow_duplicate,
            )
            for entry in notes
        ]

        try:
            note_ids = await client.invoke("addNotes", notes=payload)
        except Exception as exc:
            return handle_api_error(exc)

        # A null id means Anki refused that one note; its position in the result
        # list matches its position in the input.
        added = [note_id for note_id in note_ids if note_id is not None]
        skipped = [index for index, note_id in enumerate(note_ids) if note_id is None]

        if response_format == ResponseFormat.JSON:
            return to_json({"noteIds": note_ids, "added": len(added), "skippedIndexes": skipped})

        summary = f"Added {len(added)} of {len(note_ids)} notes to deck {deck_name!r}."
        if skipped:
            positions = ", ".join(str(index) for index in skipped)
            summary += (
                f"\n\nSkipped {len(skipped)} at index {positions} — most likely duplicates "
                "of existing notes. Re-run with allow_duplicate=True to force them in."
            )
        return summary

    @mcp.tool(annotations=READ_ONLY)
    async def anki_find_notes(
        query: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Find note ids matching an Anki search query.

        Uses Anki's own search syntax, the same one as the browser's search bar:

            deck:Python                  notes in a deck (and its subdecks)
            deck:Python::Asyncio         a specific subdeck
            tag:python::asyncio          by tag ("tag:none" = untagged)
            note:Cloze                   by note type
            "front:*GIL*"                wildcard match on a named field
            added:7                      added in the last 7 days
            is:due -is:suspended         combine terms; "-" negates

        Quote any term containing spaces. Returns ids only — pass them to
        `anki_get_notes_info` to see the actual content.

        Args:
            query: The search expression. An empty string matches nothing;
                use `"deck:*"` to match everything.
        """
        try:
            note_ids = await client.invoke("findNotes", query=query)
        except Exception as exc:
            return handle_api_error(exc)

        if response_format == ResponseFormat.JSON:
            return to_json(note_ids)

        if not note_ids:
            return f"No notes match {query!r}."
        ids = ", ".join(str(note_id) for note_id in note_ids)
        return f"{heading('Matching notes', len(note_ids))}\n\nQuery: `{query}`\n\n{ids}"

    @mcp.tool(annotations=READ_ONLY)
    async def anki_get_notes_info(
        notes: list[int],
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Fetch full details for the given note ids.

        Returns each note's model, tags, field contents (as stored — i.e. HTML),
        and the ids of the cards generated from it. Unknown ids come back as
        empty entries rather than an error.

        Markdown output truncates field values for readability; use
        `response_format="json"` to get the untouched HTML.

        Args:
            notes: Note ids, typically from `anki_find_notes`.
        """
        try:
            infos = await client.invoke("notesInfo", notes=notes)
        except Exception as exc:
            return handle_api_error(exc)

        if response_format == ResponseFormat.JSON:
            return to_json(infos)

        if not infos:
            return "No notes found."

        blocks: list[str] = []
        for info in infos:
            if not info:
                # AnkiConnect returns {} for an id that no longer exists.
                blocks.append("### (missing note)\n\nThis note id does not exist.")
                continue

            lines = [f"### Note {info.get('noteId')}"]
            lines.append(f"- **Model**: {info.get('modelName')}")
            tags = info.get("tags") or []
            lines.append(f"- **Tags**: {', '.join(tags) if tags else '_none_'}")
            cards = info.get("cards") or []
            lines.append(f"- **Cards**: {len(cards)}")
            for name, field in (info.get("fields") or {}).items():
                lines.append(f"- **{name}**: {truncate(field.get('value', ''))}")
            blocks.append("\n".join(lines))

        return f"{heading('Notes', len(infos))}\n\n" + "\n\n".join(blocks)

    @mcp.tool(annotations=DESTRUCTIVE)
    async def anki_update_note_fields(
        note_id: int,
        fields: dict[str, str],
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """Overwrite fields of an existing note.

        **Field values are HTML and are sent verbatim — do not escape them.**
        Each named field is *replaced* wholesale, not merged; fields left out of
        `fields` keep their current content. Fetch the current values with
        `anki_get_notes_info` (`response_format="json"`) before a partial edit.

        ⚠️ **This silently does nothing if the note is open in Anki's Browse
        window.** Anki refuses the edit to avoid clobbering what you are typing,
        but AnkiConnect still reports success — no error is raised, and the
        fields are simply unchanged. If an update seems to have no effect, close
        the Browse window (or click away from that note) and run it again.

        Args:
            note_id: Id of the note to modify, from `anki_find_notes`.
            fields: Field name -> new HTML content. Names must match the note's
                model exactly.
        """
        # AnkiConnect wants the id and fields wrapped in a `note` object.
        try:
            await client.invoke("updateNoteFields", note={"id": note_id, "fields": fields})
        except Exception as exc:
            return handle_api_error(exc)

        updated = ", ".join(fields)
        if response_format == ResponseFormat.JSON:
            return to_json({"noteId": note_id, "updatedFields": list(fields)})

        return (
            f"Updated fields ({updated}) on note {note_id}.\n\n"
            "Note: if the note was open in Anki's Browse window, Anki ignores the "
            "edit without reporting an error — verify with anki_get_notes_info."
        )
