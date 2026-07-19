"""Tests for the AnkiConnect wire protocol and error mapping."""

from __future__ import annotations

import httpx
import pytest

from anki_mcp.client import AnkiConnectClient
from anki_mcp.errors import AnkiConnectError, AnkiUnavailableError


async def test_invoke_sends_version_6_envelope(client: AnkiConnectClient, anki) -> None:
    """Every request is a POST of {action, version: 6, params}."""
    anki.reply(["Default"])

    await client.invoke("deckNames")

    body = anki.sent_body()
    assert body == {"action": "deckNames", "version": 6, "params": {}}


async def test_invoke_passes_params_through(client: AnkiConnectClient, anki) -> None:
    """Keyword args land in `params` under their AnkiConnect camelCase names."""
    anki.reply(1234)

    await client.invoke("createDeck", deck="Python::Asyncio")

    assert anki.sent_body()["params"] == {"deck": "Python::Asyncio"}


async def test_invoke_returns_result_field(client: AnkiConnectClient, anki) -> None:
    """The `result` field is unwrapped and returned."""
    anki.reply(["Default", "Python"])

    assert await client.invoke("deckNames") == ["Default", "Python"]


async def test_invoke_returns_none_for_null_result(client: AnkiConnectClient, anki) -> None:
    """Actions like `sync` succeed with a null result — that is not an error."""
    anki.reply(None)

    assert await client.invoke("sync") is None


async def test_non_null_error_raises(client: AnkiConnectClient, anki) -> None:
    """A non-null `error` means the request was refused, despite HTTP 200."""
    anki.fail("deck was not found: Nope")

    with pytest.raises(AnkiConnectError) as excinfo:
        await client.invoke("addNote", note={})

    assert excinfo.value.action == "addNote"
    assert "deck was not found" in str(excinfo.value)


async def test_connection_refused_explains_anki_is_closed(
    client: AnkiConnectClient, anki
) -> None:
    """The most common failure gets the most actionable message."""
    anki.raises(httpx.ConnectError("Connection refused"))

    with pytest.raises(AnkiUnavailableError) as excinfo:
        await client.invoke("version")

    message = str(excinfo.value)
    assert "Anki is probably not running" in message
    assert "2055492159" in message  # the add-on code the user needs to install


async def test_timeout_mentions_modal_dialogs(client: AnkiConnectClient, anki) -> None:
    """A hang usually means a modal dialog is blocking Anki's event loop."""
    anki.raises(httpx.ReadTimeout("timed out"))

    with pytest.raises(AnkiUnavailableError) as excinfo:
        await client.invoke("sync")

    assert "modal dialog" in str(excinfo.value)


async def test_non_json_response_is_reported(client: AnkiConnectClient, anki) -> None:
    """Something else listening on the port should not raise a bare ValueError."""
    anki.route.mock(return_value=httpx.Response(200, text="<html>not anki</html>"))

    with pytest.raises(AnkiConnectError, match="JSON envelope"):
        await client.invoke("version")


async def test_http_error_status_is_reported(client: AnkiConnectClient, anki) -> None:
    """AnkiConnect answers 200 on failure, so a non-200 is a real anomaly."""
    anki.route.mock(return_value=httpx.Response(500, text="boom"))

    with pytest.raises(AnkiConnectError, match="HTTP 500"):
        await client.invoke("version")
