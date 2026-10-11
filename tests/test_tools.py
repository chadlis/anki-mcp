"""Tests driving each tool the way an MCP client would."""

from __future__ import annotations

import json

import httpx
from fastmcp import FastMCP

from conftest import call_tool

# A field value exercising everything real cards use: cloze, inline markup, and
# a highlight.js-styled code block with quotes and angle brackets.
RICH_HTML = (
    'The GIL is released during <b>I/O</b>, so {{c1::threads}} still help.'
    '<pre><code><span class="hljs-keyword">async def</span> '
    '<span class="hljs-title">main</span>() -&gt; <i>None</i>: ...</code></pre>'
)


async def test_check_connection_reports_version(mcp: FastMCP, anki) -> None:
    anki.reply(6)

    output = await call_tool(mcp, "anki_check_connection")

    assert "API version 6" in output
    assert anki.sent_body()["action"] == "version"


async def test_check_connection_explains_closed_anki(mcp: FastMCP, anki) -> None:
    """A transport failure must come back as friendly text, not an exception."""
    anki.raises(httpx.ConnectError("Connection refused"))

    output = await call_tool(mcp, "anki_check_connection")

    assert output.startswith("Error:")
    assert "Anki is probably not running" in output


async def test_list_decks_markdown(mcp: FastMCP, anki) -> None:
    anki.reply(["Python::Asyncio", "Default"])

    output = await call_tool(mcp, "anki_list_decks")

    assert "## Decks (2)" in output
    assert "- Default" in output


async def test_list_decks_json(mcp: FastMCP, anki) -> None:
    anki.reply(["Default"])

    output = await call_tool(mcp, "anki_list_decks", response_format="json")

    assert json.loads(output) == ["Default"]


async def test_create_deck_sends_deck_param(mcp: FastMCP, anki) -> None:
    anki.reply(1600000000000)

    output = await call_tool(mcp, "anki_create_deck", deck="Python::Asyncio")

    assert anki.sent_body() == {
        "action": "createDeck",
        "version": 6,
        "params": {"deck": "Python::Asyncio"},
    }
    assert "1600000000000" in output


async def test_get_model_fields_preserves_order(mcp: FastMCP, anki) -> None:
    """Field order is meaningful — the first field drives duplicate detection."""
    anki.reply(["Text", "Back Extra"])

    output = await call_tool(mcp, "anki_get_model_fields", model_name="Cloze")

    assert anki.sent_body()["params"] == {"modelName": "Cloze"}
    assert output.index("Text") < output.index("Back Extra")


async def test_add_note_sends_html_unescaped(mcp: FastMCP, anki) -> None:
    """The whole point of this server: field HTML reaches Anki byte for byte."""
    anki.reply(1700000000000)

    await call_tool(
        mcp,
        "anki_add_note",
        deck_name="Python",
        model_name="Cloze",
        fields={"Text": RICH_HTML},
        tags=["python::asyncio"],
    )

    note = anki.sent_body()["params"]["note"]
    assert note["fields"]["Text"] == RICH_HTML
    assert note["deckName"] == "Python"
    assert note["modelName"] == "Cloze"
    assert note["tags"] == ["python::asyncio"]
    assert note["options"]["allowDuplicate"] is False


async def test_add_note_duplicate_error_is_friendly(mcp: FastMCP, anki) -> None:
    anki.fail("cannot create note because it is a duplicate")

    output = await call_tool(
        mcp,
        "anki_add_note",
        deck_name="Python",
        model_name="Basic",
        fields={"Front": "x", "Back": "y"},
    )

    assert output.startswith("Error:")
    assert "duplicate" in output


async def test_add_note_allow_duplicate_flag(mcp: FastMCP, anki) -> None:
    anki.reply(1700000000001)

    await call_tool(
        mcp,
        "anki_add_note",
        deck_name="Python",
        model_name="Basic",
        fields={"Front": "x"},
        allow_duplicate=True,
    )

    assert anki.sent_body()["params"]["note"]["options"]["allowDuplicate"] is True


async def test_add_notes_counts_null_ids_as_skipped(mcp: FastMCP, anki) -> None:
    """A null id means Anki refused that one note; the batch still succeeds."""
    anki.reply([1, None, 3])

    output = await call_tool(
        mcp,
        "anki_add_notes",
        deck_name="Python",
        model_name="Basic",
        notes=[
            {"fields": {"Front": "a"}},
            {"fields": {"Front": "b"}},
            {"fields": {"Front": "c"}},
        ],
    )

    assert "Added 2 of 3 notes" in output
    assert "index 1" in output
    assert "duplicates" in output


async def test_add_notes_applies_default_and_per_note_tags(mcp: FastMCP, anki) -> None:
    anki.reply([1, 2])

    await call_tool(
        mcp,
        "anki_add_notes",
        deck_name="Python",
        model_name="Basic",
        notes=[
            {"fields": {"Front": "a"}},
            {"fields": {"Front": "b"}, "tags": ["own"]},
        ],
        tags=["shared"],
    )

    sent = anki.sent_body()["params"]["notes"]
    assert sent[0]["tags"] == ["shared"]
    assert sent[1]["tags"] == ["own"]


async def test_find_notes_passes_query_through(mcp: FastMCP, anki) -> None:
    anki.reply([1700000000000, 1700000000001])

    output = await call_tool(mcp, "anki_find_notes", query="deck:Python tag:asyncio")

    assert anki.sent_body()["params"] == {"query": "deck:Python tag:asyncio"}
    assert "## Matching notes (2)" in output


async def test_find_notes_empty_result(mcp: FastMCP, anki) -> None:
    anki.reply([])

    output = await call_tool(mcp, "anki_find_notes", query="deck:Nope")

    assert "No notes match" in output


async def test_get_notes_info_truncates_markdown_but_not_json(mcp: FastMCP, anki) -> None:
    info = [
        {
            "noteId": 1700000000000,
            "modelName": "Cloze",
            "tags": ["python"],
            "cards": [1, 2],
            "fields": {"Text": {"value": RICH_HTML, "order": 0}},
        }
    ]
    anki.reply(info)

    markdown = await call_tool(mcp, "anki_get_notes_info", notes=[1700000000000])
    assert "Note 1700000000000" in markdown
    assert "**Model**: Cloze" in markdown
    assert markdown.rstrip().endswith("…")  # long HTML is clipped for display

    anki.reply(info)
    as_json = await call_tool(
        mcp, "anki_get_notes_info", notes=[1700000000000], response_format="json"
    )
    # JSON output must carry the untouched HTML, so it can be round-tripped.
    assert json.loads(as_json)[0]["fields"]["Text"]["value"] == RICH_HTML


async def test_get_notes_info_handles_missing_note(mcp: FastMCP, anki) -> None:
    """AnkiConnect returns an empty entry for an id that no longer exists."""
    anki.reply([{}])

    output = await call_tool(mcp, "anki_get_notes_info", notes=[42])

    assert "missing note" in output


async def test_update_note_fields_wraps_note_envelope(mcp: FastMCP, anki) -> None:
    """AnkiConnect wants {"note": {"id", "fields"}}, not flat arguments."""
    anki.reply(None)

    output = await call_tool(
        mcp,
        "anki_update_note_fields",
        note_id=1700000000000,
        fields={"Text": RICH_HTML},
    )

    assert anki.sent_body() == {
        "action": "updateNoteFields",
        "version": 6,
        "params": {"note": {"id": 1700000000000, "fields": {"Text": RICH_HTML}}},
    }
    # The silent-failure caveat has to reach the caller, since Anki reports none.
    assert "Browse window" in output


async def test_sync_reports_success(mcp: FastMCP, anki) -> None:
    anki.reply(None)

    output = await call_tool(mcp, "anki_sync")

    assert anki.sent_body()["action"] == "sync"
    assert "triggered successfully" in output


async def test_all_expected_tools_are_registered(mcp: FastMCP) -> None:
    tools = await mcp.list_tools()

    assert {tool.name for tool in tools} == {
        "anki_check_connection",
        "anki_sync",
        "anki_list_decks",
        "anki_create_deck",
        "anki_list_models",
        "anki_get_model_fields",
        "anki_add_note",
        "anki_add_notes",
        "anki_find_notes",
        "anki_get_notes_info",
        "anki_update_note_fields",
        "anki_add_tags",
        "anki_remove_tags",
        "anki_suspend",
    }
