"""Unit tests for structured output: parsing, schema validation and adapters.

Covers the "model answered, but the output is unusable" paths — malformed JSON,
missing required keys, truncated completions — and the schema plumbing of each
adapter (Ollama ``format``, OpenAI-compatible ``response_format``, Anthropic's
forced tool, Gemini's ``responseSchema``).

Every HTTP interaction uses :class:`httpx.MockTransport`; no test touches a network.
"""

from __future__ import annotations

import json

import httpx
import pytest
from ega_providers import (
    AnthropicProvider,
    CapabilityError,
    GeminiProvider,
    MalformedOutputError,
    NullProvider,
    OllamaProvider,
    OpenAICompatProvider,
    ProviderError,
    convert_json_schema,
)
from ega_providers.base import (
    GenerationSettings,
    parse_structured,
    validate_required,
)

SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["page_type", "central_entity"],
    "properties": {
        "page_type": {"type": "string"},
        "central_entity": {"type": ["string", "null"]},
        "confidence": {"type": "string"},
        "rows": {
            "type": "array",
            "items": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}},
        },
    },
}


def _settings(model: str = "test-model", **overrides) -> GenerationSettings:
    return GenerationSettings(model=model, **overrides)


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


# --------------------------------------------------------------------------- #
# parse_structured
# --------------------------------------------------------------------------- #


def test_parse_structured_reads_plain_json():
    parsed = parse_structured('{"page_type": "service", "central_entity": "Acme"}', SCHEMA)
    assert parsed == {"page_type": "service", "central_entity": "Acme"}


def test_parse_structured_accepts_a_markdown_code_fence():
    raw = '```json\n{"page_type": "article", "central_entity": null}\n```'
    assert parse_structured(raw, SCHEMA)["page_type"] == "article"


def test_parse_structured_recovers_json_from_surrounding_prose():
    raw = 'Sure! Here is the result:\n{"page_type": "glossary", "central_entity": "SLA"}\nHope that helps.'
    assert parse_structured(raw, SCHEMA)["central_entity"] == "SLA"


def test_parse_structured_tolerates_braces_inside_string_values():
    raw = '{"page_type": "docs", "central_entity": "a {b} c"}'
    assert parse_structured(raw, SCHEMA)["central_entity"] == "a {b} c"


def test_parse_structured_accepts_null_for_a_required_key():
    """PRD §22: null is the honest 'not assessed' answer, so the key may be null."""
    parsed = parse_structured('{"page_type": "service", "central_entity": null}', SCHEMA)
    assert parsed["central_entity"] is None


def test_parse_structured_rejects_missing_required_keys_as_retryable():
    with pytest.raises(MalformedOutputError) as info:
        parse_structured('{"page_type": "service"}', SCHEMA)
    assert info.value.retryable is True
    assert "central_entity" in info.value.safe_message


def test_parse_structured_rejects_non_json_output():
    with pytest.raises(MalformedOutputError, match="no complete JSON"):
        parse_structured("I could not find any structured data on this page.", SCHEMA)


def test_parse_structured_rejects_empty_output():
    with pytest.raises(MalformedOutputError, match="empty output"):
        parse_structured("   ", SCHEMA)


def test_parse_structured_rejects_truncated_json():
    with pytest.raises(MalformedOutputError, match="truncated or invalid JSON"):
        parse_structured('{"page_type": "service", "central_entity": Tru}', SCHEMA)


def test_parse_structured_rejects_an_unterminated_object():
    with pytest.raises(MalformedOutputError, match="no complete JSON"):
        parse_structured('{"page_type": "service", "central_entity": "Ac', SCHEMA)


def test_parse_structured_rejects_a_json_array_where_an_object_is_required():
    with pytest.raises(MalformedOutputError):
        parse_structured('[{"page_type": "service"}]', SCHEMA)


def test_malformed_output_snippet_is_redacted_and_short():
    secret = "sk-live-abcdef123456"
    raw = "not json at all " + secret + " " + ("z" * 900)
    with pytest.raises(MalformedOutputError) as info:
        parse_structured(raw, SCHEMA)
    assert secret not in info.value.safe_message
    assert "***REDACTED***" in info.value.safe_message
    assert len(info.value.safe_message) < 400


def test_parse_structured_never_fabricates_a_value():
    """A missing key raises; the parser does not invent a default."""
    with pytest.raises(MalformedOutputError):
        parse_structured("{}", SCHEMA)


# --------------------------------------------------------------------------- #
# validate_required
# --------------------------------------------------------------------------- #


def test_validate_required_walks_nested_objects_and_arrays():
    good = {"page_type": "x", "central_entity": None, "rows": [{"id": "a"}, {"id": "b"}]}
    validate_required(good, SCHEMA)

    with pytest.raises(MalformedOutputError, match="'id'"):
        validate_required({"page_type": "x", "central_entity": None, "rows": [{"name": "a"}]}, SCHEMA)


def test_validate_required_enforces_primitive_types():
    with pytest.raises(MalformedOutputError, match="wrong type"):
        validate_required({"page_type": 7, "central_entity": None}, SCHEMA)
    with pytest.raises(MalformedOutputError):
        validate_required({"page_type": "x", "central_entity": None, "rows": "not-an-array"}, SCHEMA)


def test_validate_required_accepts_a_declared_type_union():
    validate_required({"page_type": "x", "central_entity": None}, SCHEMA)
    validate_required({"page_type": "x", "central_entity": "Acme"}, SCHEMA)
    with pytest.raises(MalformedOutputError):
        validate_required({"page_type": "x", "central_entity": 42}, SCHEMA)


def test_validate_required_respects_additional_properties_false_only_when_declared():
    strict = {
        "type": "object",
        "additionalProperties": False,
        "required": ["a"],
        "properties": {"a": {"type": "string"}},
    }
    with pytest.raises(MalformedOutputError, match="Unexpected key"):
        validate_required({"a": "1", "b": "2"}, strict)
    # Without the flag, extra keys are tolerated (models often add them).
    validate_required({"a": "1", "b": "2"}, {"type": "object", "properties": {"a": {"type": "string"}}})


def test_validate_required_checks_integer_and_boolean_strictly():
    schema = {"type": "object", "properties": {"n": {"type": "integer"}, "flag": {"type": "boolean"}}}
    validate_required({"n": 3, "flag": True}, schema)
    with pytest.raises(MalformedOutputError):
        validate_required({"n": True}, schema)  # bool is not an integer here
    with pytest.raises(MalformedOutputError):
        validate_required({"flag": "yes"}, schema)


# --------------------------------------------------------------------------- #
# Ollama
# --------------------------------------------------------------------------- #


async def test_ollama_generate_structured_passes_the_schema_as_format():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200, json={"message": {"content": '{"page_type": "service", "central_entity": "Acme"}'}}
        )

    provider = OllamaProvider(model="llama3.2", base_url="http://localhost:11434", client=_client(handler))
    data = await provider.generate_structured(
        schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("llama3.2")
    )
    assert data["central_entity"] == "Acme"
    assert captured["format"] == SCHEMA  # the JSON schema itself, not a bare "json"
    assert captured["model"] == "llama3.2"
    assert captured["stream"] is False
    await provider.aclose()


async def test_ollama_falls_back_to_format_json_when_the_server_rejects_the_schema():
    seen_formats: list[object] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        seen_formats.append(payload.get("format"))
        if len(seen_formats) == 1:
            return httpx.Response(400, json={"error": "format not supported"})
        return httpx.Response(
            200, json={"message": {"content": '{"page_type": "service", "central_entity": null}'}}
        )

    provider = OllamaProvider(model="m", client=_client(handler))
    result = await provider.generate_structured_result(
        schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
    )
    assert seen_formats[0] == SCHEMA
    assert seen_formats[1] == "json"
    assert any("fallback" in note.lower() or "fell back" in note for note in result.notes)
    await provider.aclose()


async def test_ollama_rejects_a_truncated_completion():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {"content": '{"page_type": "service", "central_entity": "'},
                "done": False,
                "done_reason": "length",
            },
        )

    provider = OllamaProvider(model="m", client=_client(handler))
    with pytest.raises(MalformedOutputError, match="truncated"):
        await provider.generate_structured_result(
            schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
        )
    await provider.aclose()


async def test_ollama_rejects_an_empty_message():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "   "}})

    provider = OllamaProvider(model="m", client=_client(handler))
    with pytest.raises(MalformedOutputError, match="empty message"):
        await provider.generate_structured(
            schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
        )
    await provider.aclose()


async def test_ollama_generate_text_returns_raw_text():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "plain answer"}})

    provider = OllamaProvider(model="m", client=_client(handler))
    text = await provider.generate_text(
        messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
    )
    assert text == "plain answer"
    await provider.aclose()


async def test_ollama_refuses_a_call_without_a_model_id():
    provider = OllamaProvider(model="", client=_client(lambda request: httpx.Response(200, json={})))
    with pytest.raises(ProviderError, match="No model ID"):
        await provider.generate_text(
            messages=[{"role": "user", "content": "hi"}], settings=GenerationSettings(model="")
        )
    await provider.aclose()


# --------------------------------------------------------------------------- #
# OpenAI-compatible
# --------------------------------------------------------------------------- #


async def test_openai_compat_uses_strict_json_schema_first():
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": '{"page_type": "service", "central_entity": "Acme"}'},
                        "finish_reason": "stop",
                    }
                ]
            },
        )

    provider = OpenAICompatProvider(
        base_url="http://127.0.0.1:8000/v1", model="local-model", client=_client(handler)
    )
    data = await provider.generate_structured(
        schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("local-model")
    )
    assert data["page_type"] == "service"
    response_format = captured["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["schema"] == SCHEMA
    assert captured["model"] == "local-model"
    await provider.aclose()


async def test_openai_compat_downgrades_response_format_and_records_notes():
    formats: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        rf = payload.get("response_format")
        formats.append(None if rf is None else rf["type"])
        if len(formats) < 3:
            return httpx.Response(400, json={"error": "unsupported response_format"})
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"page_type": "docs", "central_entity": null}'},
                     "finish_reason": "stop"}
                ]
            },
        )

    provider = OpenAICompatProvider(base_url="http://127.0.0.1:8000/v1", model="m", client=_client(handler))
    result = await provider.generate_structured_result(
        schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
    )
    assert formats == ["json_schema", "json_object", None]
    assert len(result.notes) == 2
    assert result.data["page_type"] == "docs"
    await provider.aclose()


async def test_openai_compat_rejects_output_truncated_at_max_tokens():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"page_type":'}, "finish_reason": "length"}]},
        )

    provider = OpenAICompatProvider(base_url="http://127.0.0.1:8000/v1", model="m", client=_client(handler))
    with pytest.raises(MalformedOutputError, match="truncated"):
        await provider.generate_structured(
            schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
        )
    await provider.aclose()


async def test_openai_compat_requires_a_base_url():
    with pytest.raises(ProviderError, match="base_url is required"):
        OpenAICompatProvider(base_url="", model="m")


async def test_openai_compat_sends_the_api_key_only_when_configured():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update({k.lower(): v for k, v in request.headers.items()})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"page_type": "x", "central_entity": null}'}}]},
        )

    provider = OpenAICompatProvider(
        base_url="http://127.0.0.1:8000/v1", model="m", api_key="local-secret-key", client=_client(handler)
    )
    await provider.generate_structured(
        schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
    )
    assert captured["authorization"] == "Bearer local-secret-key"
    assert "local-secret-key" not in repr(provider)
    await provider.aclose()


# --------------------------------------------------------------------------- #
# Anthropic
# --------------------------------------------------------------------------- #


async def test_anthropic_forces_a_single_json_tool():
    captured: dict[str, object] = {}
    headers: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        headers.update({k.lower(): v for k, v in request.headers.items()})
        return httpx.Response(
            200,
            json={
                "content": [
                    {"type": "tool_use", "name": "emit_json", "input": {"page_type": "service", "central_entity": "Acme"}}
                ],
                "stop_reason": "tool_use",
            },
        )

    provider = AnthropicProvider(api_key="sk-ant-secret", model="claude-x", client=_client(handler))
    data = await provider.generate_structured(
        schema=SCHEMA,
        messages=[
            {"role": "system", "content": "system prompt"},
            {"role": "user", "content": "hi"},
        ],
        settings=_settings("claude-x"),
    )
    assert data["page_type"] == "service"
    assert captured["tool_choice"] == {"type": "tool", "name": "emit_json"}
    assert captured["tools"][0]["input_schema"] == SCHEMA
    assert captured["system"] == "system prompt"
    assert headers["anthropic-version"]
    assert headers["x-api-key"] == "sk-ant-secret"
    await provider.aclose()


async def test_anthropic_rejects_a_response_without_the_forced_tool():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "I would rather explain."}], "stop_reason": "end_turn"},
        )

    provider = AnthropicProvider(api_key="k", model="m", client=_client(handler))
    with pytest.raises(MalformedOutputError, match="tool_use"):
        await provider.generate_structured(
            schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
        )
    await provider.aclose()


async def test_anthropic_rejects_a_max_tokens_stop_reason():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"content": [{"type": "tool_use", "name": "emit_json", "input": {}}], "stop_reason": "max_tokens"},
        )

    provider = AnthropicProvider(api_key="k", model="m", client=_client(handler))
    with pytest.raises(MalformedOutputError, match="truncated"):
        await provider.generate_structured(
            schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
        )
    await provider.aclose()


async def test_anthropic_validates_the_tool_input_against_the_schema():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [{"type": "tool_use", "name": "emit_json", "input": {"page_type": "service"}}],
                "stop_reason": "tool_use",
            },
        )

    provider = AnthropicProvider(api_key="k", model="m", client=_client(handler))
    with pytest.raises(MalformedOutputError, match="central_entity"):
        await provider.generate_structured(
            schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
        )
    await provider.aclose()


async def test_anthropic_generate_text_concatenates_text_blocks():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"content": [{"type": "text", "text": "hello "}, {"type": "text", "text": "world"}]},
        )

    provider = AnthropicProvider(api_key="k", model="m", client=_client(handler))
    assert await provider.generate_text(
        messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
    ) == "hello world"
    await provider.aclose()


# --------------------------------------------------------------------------- #
# Gemini
# --------------------------------------------------------------------------- #


async def test_gemini_sends_the_schema_and_keeps_the_key_out_of_the_url():
    captured: dict[str, object] = {}
    seen_url = ""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal seen_url
        seen_url = str(request.url)
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": '{"page_type": "service", "central_entity": "Acme"}'}]}}
                ]
            },
        )

    provider = GeminiProvider(api_key="AIzaSecretKey", model="gemini-2.0-flash", client=_client(handler))
    data = await provider.generate_structured(
        schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("gemini-2.0-flash")
    )
    assert data["central_entity"] == "Acme"
    generation_config = captured["generationConfig"]
    assert generation_config["responseMimeType"] == "application/json"
    assert "responseSchema" in generation_config
    assert "AIzaSecretKey" not in seen_url
    assert "/v1beta/models/gemini-2.0-flash:generateContent" in seen_url
    await provider.aclose()


async def test_gemini_rejects_a_truncated_candidate():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": '{"page_type":'}]}, "finishReason": "MAX_TOKENS"}
                ]
            },
        )

    provider = GeminiProvider(api_key="k", model="m", client=_client(handler))
    with pytest.raises(MalformedOutputError, match="truncated"):
        await provider.generate_structured(
            schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
        )
    await provider.aclose()


async def test_gemini_refuses_safety_blocked_output_without_inventing_an_answer():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}})

    provider = GeminiProvider(api_key="k", model="m", client=_client(handler))
    with pytest.raises(ProviderError, match="no candidates"):
        await provider.generate_structured(
            schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=_settings("m")
        )
    await provider.aclose()


def test_gemini_schema_conversion_inlines_refs_and_maps_nullable_unions():
    schema = {
        "$defs": {"Row": {"type": "object", "required": ["id"], "properties": {"id": {"type": "string"}}}},
        "type": "object",
        "properties": {
            "rows": {"type": "array", "items": {"$ref": "#/$defs/Row"}},
            "note": {"type": ["string", "null"], "pattern": "^x$"},
            "count": {"type": "integer", "minimum": 0},
        },
    }
    converted = convert_json_schema(schema)
    assert "$defs" not in converted
    assert "$ref" not in json.dumps(converted)
    rows = converted["properties"]["rows"]
    assert rows["type"] == "array"
    assert rows["items"]["properties"]["id"]["type"] == "string"
    assert converted["properties"]["note"]["nullable"] is True
    assert converted["properties"]["note"]["type"] == "string"
    assert "pattern" not in converted["properties"]["note"]  # unsupported → dropped
    assert converted["properties"]["count"]["minimum"] == 0


def test_gemini_schema_conversion_handles_enum_and_description():
    converted = convert_json_schema(
        {"type": "object", "properties": {"s": {"type": "string", "enum": ["a", "b"], "description": "d"}}}
    )
    assert converted["properties"]["s"]["enum"] == ["a", "b"]
    assert converted["properties"]["s"]["description"] == "d"


# --------------------------------------------------------------------------- #
# Deterministic-only mode
# --------------------------------------------------------------------------- #


async def test_null_provider_structured_call_raises_instead_of_fabricating():
    provider = NullProvider()
    with pytest.raises(CapabilityError):
        await provider.generate_structured(
            schema=SCHEMA, messages=[{"role": "user", "content": "hi"}], settings=GenerationSettings(model="")
        )


async def test_embedding_is_a_declared_capability_gap():
    provider = OllamaProvider(model="m", client=_client(lambda request: httpx.Response(200, json={})))
    with pytest.raises(CapabilityError, match="embeddings"):
        await provider.embed(["text"], _settings("m"))
    await provider.aclose()
