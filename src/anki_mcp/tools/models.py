"""Note type ("model") tools.

Anki calls them *note types* in the UI and *models* in its API. A model defines
the named fields a note holds (`Front`/`Back`, `Text`/`Back Extra`, …) and the
card templates generated from them.
"""

from __future__ import annotations

from fastmcp import FastMCP

from ..client import AnkiConnectClient
from ..errors import handle_api_error
from ..formatting import ResponseFormat, bullet_list, to_json
from ._common import READ_ONLY


def register(mcp: FastMCP, client: AnkiConnectClient) -> None:
    """Register the model tools on `mcp`, closing over `client`."""

    @mcp.tool(annotations=READ_ONLY)
    async def anki_list_models(
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List every note type (model) in the collection.

        Typical built-ins: `"Basic"`, `"Basic (and reversed card)"`, `"Cloze"`.
        Use `anki_get_model_fields` next to learn a model's field names before
        adding a note with it.
        """
        try:
            models = await client.invoke("modelNames")
        except Exception as exc:
            return handle_api_error(exc)

        if response_format == ResponseFormat.JSON:
            return to_json(models)

        return bullet_list("Note types", sorted(models))

    @mcp.tool(annotations=READ_ONLY)
    async def anki_get_model_fields(
        model_name: str,
        response_format: ResponseFormat = ResponseFormat.MARKDOWN,
    ) -> str:
        """List a note type's field names, in template order.

        These are the exact keys `anki_add_note` expects in its `fields` dict —
        they are case-sensitive and space-sensitive (`"Back Extra"`, not
        `"back_extra"`).

        Args:
            model_name: Note type name, e.g. `"Cloze"`.
        """
        try:
            fields = await client.invoke("modelFieldNames", modelName=model_name)
        except Exception as exc:
            return handle_api_error(exc)

        if response_format == ResponseFormat.JSON:
            return to_json({"modelName": model_name, "fields": fields})

        # Field order is meaningful (the first field is the sort field and drives
        # duplicate detection), so this list is deliberately left unsorted.
        return bullet_list(f"Fields of {model_name!r}", fields)
