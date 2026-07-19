"""Shared fixtures. No test ever touches the network or a real Anki instance."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
import respx
from fastmcp import FastMCP

from anki_mcp.client import AnkiConnectClient
from anki_mcp.config import Settings
from anki_mcp.server import build_server

# Deliberately not the default port: if a test ever escaped respx and hit the
# network, it would fail loudly instead of silently talking to a real Anki.
TEST_URL = "http://localhost:18765"


@pytest.fixture
def settings() -> Settings:
    """Settings pointing at the mock endpoint, with a short timeout."""
    return Settings(anki_connect_url=TEST_URL, timeout=5.0)


@pytest.fixture
def client(settings: Settings) -> AnkiConnectClient:
    """An AnkiConnectClient wired to the mock endpoint."""
    return AnkiConnectClient(settings)


@pytest.fixture
def mcp(settings: Settings) -> FastMCP:
    """A fully built server whose client talks to the mock endpoint."""
    return build_server(settings)


@pytest.fixture
def anki(settings: Settings):
    """Mock the AnkiConnect endpoint.

    Yields a helper object with:
      - `reply(result)` — answer every call with `{"result": ..., "error": null}`
      - `fail(message)` — answer with a non-null `error`
      - `route` — the respx route, for asserting on the request that was sent
      - `sent_body()` — the decoded JSON body of the last request
    """
    with respx.mock(assert_all_called=False) as mock:
        route = mock.post(settings.anki_connect_url)

        class Anki:
            def __init__(self) -> None:
                self.route = route

            def reply(self, result: Any) -> None:
                route.mock(return_value=httpx.Response(200, json={"result": result, "error": None}))

            def fail(self, message: str) -> None:
                envelope = {"result": None, "error": message}
                route.mock(return_value=httpx.Response(200, json=envelope))

            def raises(self, exc: Exception) -> None:
                route.mock(side_effect=exc)

            def sent_body(self) -> dict[str, Any]:
                return json.loads(route.calls.last.request.content)

        yield Anki()


async def call_tool(mcp: FastMCP, name: str, **args: Any) -> str:
    """Invoke a tool the way an MCP client would and return its text output.

    `call_tool` returns a ToolResult; a tool declared `-> str` puts its value in
    `.structured_content["result"]`.
    """
    result = await mcp.call_tool(name, args)
    return result.structured_content["result"]
