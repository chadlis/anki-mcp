"""The AnkiConnect HTTP client.

## The AnkiConnect protocol in one paragraph

AnkiConnect is an Anki add-on that opens a small HTTP server on
`http://localhost:8765`. It has **one endpoint** — the root — and **one verb**,
POST. Every call, whether it lists decks or creates a note, sends the same body
shape:

    {"action": "deckNames", "version": 6, "params": {}}

and always gets back the same envelope, **always with HTTP status 200**:

    {"result": ["Default", "Python"], "error": null}

Failures are reported in the body, not in the status code: on error, `result` is
`null` and `error` holds a message. So `raise_for_status()` is nearly useless
here — the real check is `error is not None`.

That regularity is why this whole module is a single `invoke()` method: the tool
layer never builds a request or parses an envelope itself.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any

import httpx

from .config import Settings
from .errors import AnkiConnectError, timed_out, unavailable

# The API version this client speaks. AnkiConnect has been on 6 for years; it is
# sent on every request and the add-on rejects anything it does not support.
ANKICONNECT_API_VERSION = 6


class AnkiConnectClient:
    """A thin, reusable wrapper around the AnkiConnect endpoint.

    Holds one `httpx.AsyncClient` for the whole server lifetime (connection
    reuse), exactly like `YnabClient` in the ynab-mcp reference repo.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.AsyncClient(timeout=settings.timeout)

    @property
    def url(self) -> str:
        """The AnkiConnect endpoint this client talks to."""
        return self._settings.anki_connect_url

    async def invoke(self, action: str, **params: Any) -> Any:
        """Send one AnkiConnect request and return its `result` field.

        This is the only function in the codebase that knows the wire format.

        Args:
            action: The AnkiConnect action name, e.g. `"deckNames"`, `"addNote"`.
            **params: The action's parameters, passed through verbatim as the
                `params` object. Keys use AnkiConnect's own camelCase spelling
                (`deckName`, `modelName`, …), not Python's snake_case.

        Returns:
            Whatever the action puts in `result` — a list, a dict, an int, or
            `None` for actions like `sync` that return nothing on success.

        Raises:
            AnkiUnavailableError: Anki is not running, the add-on is missing, or
                the request timed out.
            AnkiConnectError: Anki answered with a non-null `error`.
        """
        payload: dict[str, Any] = {
            "action": action,
            "version": ANKICONNECT_API_VERSION,
            # Always send `params`, even empty: some actions tolerate its
            # absence, but sending it uniformly keeps the wire format one shape.
            "params": params,
        }

        try:
            response = await self._client.post(self.url, json=payload)
        except httpx.TimeoutException as exc:
            raise timed_out(self.url, self._settings.timeout) from exc
        except httpx.ConnectError as exc:
            # Connection refused is the signature of "Anki is closed" — by far
            # the most common failure, so it gets the most actionable message.
            raise unavailable(self.url) from exc

        if response.status_code != httpx.codes.OK:
            body = response.text[:200]
            raise AnkiConnectError(action, f"HTTP {response.status_code} from AnkiConnect: {body}")

        try:
            envelope = response.json()
        except ValueError as exc:
            # Something answered on port 8765, but it was not AnkiConnect.
            raise AnkiConnectError(
                action, f"expected a JSON envelope, got: {response.text[:200]!r}"
            ) from exc

        # The envelope always carries both keys; a missing `error` means we are
        # not talking to AnkiConnect v6.
        error = envelope.get("error")
        if error is not None:
            raise AnkiConnectError(action, str(error))

        return envelope.get("result")

    async def aclose(self) -> None:
        """Close the underlying HTTP connection pool."""
        await self._client.aclose()

    async def __aenter__(self) -> AnkiConnectClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()
