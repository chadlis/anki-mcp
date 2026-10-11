"""Tests for the tag and suspension tools."""

from __future__ import annotations

import json

import httpx
from fastmcp import FastMCP

from conftest import call_tool


async def test_add_tags_joins_with_spaces(mcp: FastMCP, anki) -> None:
    anki.reply(None)

    output = await call_tool(mcp, "anki_add_tags", notes=[1, 2], tags=["attend::M2", "x"])

    assert anki.sent_body() == {
        "action": "addTags",
        "version": 6,
        "params": {"notes": [1, 2], "tags": "attend::M2 x"},
    }
    assert "2 note(s)" in output


async def test_add_tags_rejects_space_without_calling_anki(mcp: FastMCP, anki) -> None:
    anki.reply(None)

    output = await call_tool(mcp, "anki_add_tags", notes=[1], tags=["two words"])

    assert output.startswith("Error:")
    assert not anki.route.called


async def test_remove_tags(mcp: FastMCP, anki) -> None:
    anki.reply(None)

    await call_tool(mcp, "anki_remove_tags", notes=[3], tags=["focus::3fils"])

    assert anki.sent_body()["action"] == "removeTags"
    assert anki.sent_body()["params"] == {"notes": [3], "tags": "focus::3fils"}


def _replies(anki, *results) -> None:
    anki.route.mock(
        side_effect=[httpx.Response(200, json={"result": r, "error": None}) for r in results]
    )


async def test_suspend_resolves_cards_then_suspends(mcp: FastMCP, anki) -> None:
    _replies(anki, [10, 11, 12], True)

    output = await call_tool(mcp, "anki_suspend", query="nid:1,2")

    first = json.loads(anki.route.calls[0].request.content)
    second = json.loads(anki.route.calls[1].request.content)
    assert first["action"] == "findCards" and first["params"] == {"query": "nid:1,2"}
    assert second["action"] == "suspend" and second["params"] == {"cards": [10, 11, 12]}
    assert "Suspended 3 card(s)" in output


async def test_unsuspend(mcp: FastMCP, anki) -> None:
    _replies(anki, [10], True)

    await call_tool(mcp, "anki_suspend", query="tag:attend::M1", suspend=False)

    assert json.loads(anki.route.calls[1].request.content)["action"] == "unsuspend"


async def test_suspend_no_match_makes_one_call(mcp: FastMCP, anki) -> None:
    anki.reply([])

    output = await call_tool(mcp, "anki_suspend", query="nid:999")

    assert anki.route.call_count == 1
    assert "nothing changed" in output


async def test_suspend_error_is_text(mcp: FastMCP, anki) -> None:
    anki.fail("collection is not available")

    output = await call_tool(mcp, "anki_suspend", query="deck:*")

    assert output.startswith("Error:")
