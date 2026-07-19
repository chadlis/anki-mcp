"""Error types and the single place where exceptions become user-facing text.

Every tool wraps its body in `try/except Exception` and returns
`handle_api_error(exc)`. An MCP client should get a sentence telling it what to
do next, never a stack trace.
"""

from __future__ import annotations

import httpx

# The AnkiConnect add-on's ID on ankiweb.net. Users install it by pasting this
# code into Anki: Tools -> Add-ons -> Get Add-ons.
ANKICONNECT_ADDON_CODE = "2055492159"

_NOT_RUNNING = (
    "Cannot reach AnkiConnect at {url}. Anki is probably not running, or the "
    f"AnkiConnect add-on (code {ANKICONNECT_ADDON_CODE}) is not installed. "
    "Start Anki — it must stay open — and try again."
)

_TIMED_OUT = (
    "AnkiConnect at {url} did not answer within {timeout:g}s. Anki stops serving "
    "requests while a modal dialog is open (an import prompt, a sync conflict, "
    "the add-on manager…) — check Anki's window, dismiss any dialog, and retry."
)


class AnkiConnectError(RuntimeError):
    """AnkiConnect answered with a non-null `error` field.

    This is a *refused* request, not a transport failure: Anki understood the
    action and declined it (unknown deck, duplicate note, bad model name…).
    """

    def __init__(self, action: str, message: str) -> None:
        self.action = action
        self.message = message
        super().__init__(f"AnkiConnect refused action {action!r}: {message}")


class AnkiUnavailableError(RuntimeError):
    """Anki could not be reached at all (not running, add-on missing, timeout)."""


def handle_api_error(exc: Exception) -> str:
    """Map any exception raised while talking to Anki to one friendly line."""
    if isinstance(exc, AnkiUnavailableError | AnkiConnectError):
        # Already phrased for a human by the client — pass it through.
        return f"Error: {exc}"

    if isinstance(exc, httpx.TimeoutException):
        return f"Error: request to Anki timed out ({exc})."

    if isinstance(exc, httpx.ConnectError):
        return f"Error: cannot connect to Anki ({exc})."

    if isinstance(exc, httpx.HTTPError):
        return f"Error: HTTP failure talking to Anki: {exc}"

    return f"Error: {exc}"


def unavailable(url: str) -> AnkiUnavailableError:
    """Build the 'Anki is not running' error for `url`."""
    return AnkiUnavailableError(_NOT_RUNNING.format(url=url))


def timed_out(url: str, timeout: float) -> AnkiUnavailableError:
    """Build the 'AnkiConnect did not answer' error for `url`."""
    return AnkiUnavailableError(_TIMED_OUT.format(url=url, timeout=timeout))
