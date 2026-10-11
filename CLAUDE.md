# CLAUDE.md

Guidance for Claude Code (and other agents) working in this repository.

## What this is

An MCP server that exposes a local **Anki** collection to MCP clients (Claude
Desktop, VS Code) through the **AnkiConnect** add-on. Read tools (decks, note
types, note search and details) and write tools (create deck, add notes, update
fields, sync). Managed with **uv**.

## Commands

```bash
uv sync --extra dev          # install runtime + dev dependencies
uv run anki-mcp              # run the server (stdio transport by default)
uv run pytest                # run the test suite (no network — HTTP is mocked)
uv run pytest -q tests/test_tools.py::test_add_note_sends_html_unescaped
uv run ruff check .          # lint
uv run ruff check --fix .    # lint + autofix
uv run fastmcp inspect src/anki_mcp/server.py:mcp
uv run python scripts/smoke_client.py   # end-to-end, needs Anki running
```

If a stale `VIRTUAL_ENV` from another project is exported in the shell, prefix
uv commands with `env -u VIRTUAL_ENV` so uv uses this project's `.venv`.

## The AnkiConnect protocol

AnkiConnect opens an HTTP server on `http://localhost:8765` with **one endpoint**
and **one verb**. Every call looks like this:

```
POST /  {"action": "deckNames", "version": 6, "params": {}}
->      {"result": ["Default"], "error": null}
```

Two consequences that shape the whole codebase:

- **Failures come back as HTTP 200** with a non-null `error`. `raise_for_status()`
  is nearly useless; the real check is `error is not None`.
- Because every call is the same shape, the entire protocol lives in one
  function — `AnkiConnectClient.invoke()`. Nothing else builds a request or
  parses an envelope.

Params use AnkiConnect's camelCase (`deckName`, `modelName`); tools expose
snake_case and translate.

## Architecture

Source lives under `src/anki_mcp/` (src-layout, installed package):

- `config.py` — `Settings.from_env()` resolves all runtime config from env vars
  (loads a local `.env` if present). Everything has a working default.
- `client.py` — `AnkiConnectClient` wraps a **single reusable**
  `httpx.AsyncClient`. `invoke(action, **params)` is the only function that
  knows the wire format.
- `errors.py` — `handle_api_error()` maps exceptions to one friendly message;
  `unavailable()` / `timed_out()` build the two transport failures.
- `formatting.py` — `ResponseFormat` (markdown | json), `to_json()`,
  `bullet_list()`, `truncate()`.
- `server.py` — `build_server()` creates the `FastMCP` instance and registers
  tools. The module-level `mcp = build_server()` is used by both `main()`
  (console entry point, picks the transport) and any `module:object` target.
  It imports **absolutely** (`from anki_mcp.client import …`) because
  `fastmcp inspect` loads the file as a standalone module, where relative
  imports have no parent package.
- `tools/` — one module per domain (`system`, `decks`, `models`, `notes`,
  `organize` — tags on notes, suspension on cards). Each
  exposes `register(mcp, client)`; `tools/__init__.py:register_all()` wires them
  all. Shared annotation dicts live in `tools/_common.py`.

To add a tool: create/extend a module in `tools/`, define it inside `register()`
as a closure over `client`, and ensure the module is called from `register_all`.

## Conventions

- **Fields are HTML, and are never escaped.** An Anki field holds an HTML
  fragment. `anki_add_note`, `anki_add_notes` and `anki_update_note_fields` pass
  values through byte for byte — no escaping, no sanitizing, no whitespace
  normalization. This is deliberate: the collection uses cloze, inline markup and
  highlight.js `<span class="hljs-…">` blocks. Never add "helpful" escaping.
- **Docstrings are the API.** They are what the model reads to choose a tool and
  its arguments, so protocol gotchas belong there, not only in this file.
- Every tool wraps its body in `try/except` and returns `handle_api_error(e)` —
  never let an exception escape to the client.
- Tool output is Markdown by default; `response_format="json"` returns the raw
  payload (and untruncated field HTML).
- Nothing may `print()` to stdout: under stdio transport that stream carries
  JSON-RPC and stray output corrupts the protocol.
- Code, comments, and docstrings are in **English**.

## Gotchas worth remembering

- `updateNoteFields` **fails silently** when the note is open in Anki's Browse
  window: Anki skips the edit and AnkiConnect still reports success.
- `addNote` errors on a duplicate; `addNotes` returns `null` at that note's index
  instead, so the batch partially succeeds.
- Anki stops serving AnkiConnect requests while a **modal dialog** is open, which
  surfaces as a timeout.
- Deck and tag nesting both use `::`. Tags cannot contain spaces.
- Tags are on **notes**, suspension is on **cards**: `addTags`/`removeTags` take
  note ids and one space-separated string; `suspend`/`unsuspend` take card ids,
  which `anki_suspend` resolves from a query with `findCards`.

## Environment variables

- `ANKI_CONNECT_URL` — default `http://localhost:8765`.
- `ANKI_TIMEOUT` — HTTP timeout in seconds (default `30`).
- `MCP_TRANSPORT` — `stdio` (default) or `http` (streamable-http, endpoint `/mcp`).
- `HOST` / `PORT` — bind address for the `http` transport (default `0.0.0.0:8000`).

## Security

AnkiConnect is **unauthenticated** — anything that reaches port 8765 can read and
modify the collection. It is localhost-only, which is what makes that acceptable;
never expose the port. `.env` is gitignored but holds no secrets by default.

Remote hosting is not useful here: AnkiConnect is only reachable on the machine
where Anki runs, so an `MCP_TRANSPORT=http` instance deployed elsewhere would
have nothing to talk to. The toggle exists for structural parity only.

## Testing notes

Tests mock HTTP with `respx` and never touch a real Anki. The `anki` fixture in
`conftest.py` exposes `reply()`, `fail()`, `raises()` and `sent_body()` so tests
can assert on the exact envelope sent. `test_tools.py` drives tools through
`FastMCP.call_tool(name, args)`, which returns a `ToolResult` whose
`.structured_content["result"]` holds the tool's text output.

The fixtures point at port **18765**, not the real 8765: if a test ever escaped
respx it would fail loudly instead of silently mutating a live collection.
