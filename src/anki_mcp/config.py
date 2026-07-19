"""Runtime configuration, resolved from environment variables.

All settings have sensible defaults, so the server runs with no `.env` at all as
long as Anki is on the same machine with AnkiConnect on its default port.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# AnkiConnect's default bind address. The add-on listens on localhost only.
DEFAULT_ANKI_CONNECT_URL = "http://localhost:8765"
DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of the environment, read once at startup."""

    anki_connect_url: str = DEFAULT_ANKI_CONNECT_URL
    timeout: float = DEFAULT_TIMEOUT
    transport: str = "stdio"
    host: str = "0.0.0.0"
    port: int = 8000

    @classmethod
    def from_env(cls) -> Settings:
        """Build settings from the process environment, loading `.env` if present.

        `load_dotenv` never overrides variables already exported in the shell, so
        an explicit `MCP_TRANSPORT=http uv run anki-mcp` still wins over `.env`.
        """
        load_dotenv()

        return cls(
            anki_connect_url=os.getenv("ANKI_CONNECT_URL", DEFAULT_ANKI_CONNECT_URL).rstrip("/"),
            timeout=_float_env("ANKI_TIMEOUT", DEFAULT_TIMEOUT),
            # Normalized here so `main()` only ever compares against "http".
            transport=os.getenv("MCP_TRANSPORT", "stdio").strip().lower(),
            host=os.getenv("HOST", "0.0.0.0"),
            port=_int_env("PORT", 8000),
        )


def _float_env(name: str, default: float) -> float:
    """Read a float env var, falling back to `default` if unset or malformed."""
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    """Read an int env var, falling back to `default` if unset or malformed."""
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default
