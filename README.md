# anki-mcp

An MCP server that exposes your local Anki collection to MCP clients such as Claude Desktop and VS Code, through the [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on.

Note fields are HTML and are passed through verbatim, so cards can be generated with cloze deletions, bold/italic, and highlight.js-styled code blocks.

## Tools

**Read**

- `anki_check_connection` — verify Anki is running and AnkiConnect is reachable
- `anki_list_decks` — every deck (`::` denotes nesting)
- `anki_list_models` — every note type
- `anki_get_model_fields` — a note type's field names, in template order
- `anki_find_notes` — note ids matching an Anki search query
- `anki_get_notes_info` — full note details: model, tags, fields, cards

**Write**

- `anki_create_deck` — create a deck, including missing parents
- `anki_add_note` — add one note (fields are HTML, sent unescaped)
- `anki_add_notes` — add a batch sharing one deck and note type
- `anki_update_note_fields` — overwrite fields of an existing note
- `anki_sync` — sync the collection with AnkiWeb

## Requirements

- uv
- Anki, **running** — the server talks to the live application, not the collection file
- The AnkiConnect add-on: Anki → Tools → Add-ons → Get Add-ons → code `2055492159`, then restart Anki

## Setup

```
uv sync
cp .env.example .env
```

`.env` (all optional — the defaults work for a standard local Anki):
```
ANKI_CONNECT_URL=http://localhost:8765
ANKI_TIMEOUT=30
```

Run it:
```
uv run anki-mcp
```

Check it can reach Anki:
```
uv run python scripts/smoke_client.py
```

## Use with Claude Desktop

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "anki": {
      "command": "uv",
      "args": ["run", "--directory", "/absolute/path/to/anki-mcp", "anki-mcp"]
    }
  }
}
```

No secrets to pass — AnkiConnect is unauthenticated and local.

## Remote (HTTP) hosting

Set `MCP_TRANSPORT=http` to serve over streamable-http (endpoint `/mcp`):
```
MCP_TRANSPORT=http HOST=0.0.0.0 PORT=8000 uv run anki-mcp
```

**This is of limited use here.** AnkiConnect binds to localhost on the machine where Anki runs, so a remotely hosted instance of this server has nothing to connect to — every tool would fail. The transport toggle exists for structural parity with a normal MCP server; making it genuinely useful would need a tunnel back to the desktop (a WebSocket relay or similar), which is out of scope. Run it locally over stdio.

## Conventions

- **Fields are HTML.** Values in `fields` are sent to Anki byte for byte — no escaping, no sanitizing. `"<b>x</b>"` renders as a bold *x*; to show a literal `<`, send `&lt;`.
- **Cloze** deletions use `{{c1::...}}` and require a cloze note type; the syntax is inert on `"Basic"`.
- **Field names** are case- and space-sensitive (`"Back Extra"`). Check them with `anki_get_model_fields` before adding notes.
- **Duplicates**: `anki_add_note` fails on a duplicate first field; `anki_add_notes` skips the offending note and reports its index. Both accept `allow_duplicate=True`.
- **`anki_update_note_fields` silently does nothing** if the note is open in Anki's Browse window — Anki refuses the edit but reports success. Close the browser and retry.
- Tool output is Markdown by default; pass `response_format="json"` for the raw payload (and for untruncated field HTML).
- Anki must stay open, and it stops serving requests while a modal dialog is up.

## Development

```
uv sync --extra dev
uv run pytest          # tests (HTTP mocked, no network, no real Anki)
uv run ruff check .    # lint
uv run ruff check --fix .
uv run fastmcp inspect src/anki_mcp/server.py:mcp
```

## Security

AnkiConnect has **no authentication**: anything that can reach port 8765 can read and modify your collection. That is acceptable because it listens on localhost only — do not expose that port, and do not run this server on an untrusted machine. `.env` is gitignored, though it holds no secrets by default.

This server can create, overwrite, and sync notes. Back up your collection (Anki → File → Export) before letting an agent make bulk changes.

## License

MIT
