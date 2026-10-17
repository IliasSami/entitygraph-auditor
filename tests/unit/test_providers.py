"""Unit tests for the provider adapters, registry, catalog and error redaction.

Covers PRD FR-21 (adapter set, cost warnings, no silent model changes, secret
redaction) and FR-22 (deterministic-only mode, health checks, never fabricate).

Every HTTP interaction uses :class:`httpx.MockTransport` — no test opens a socket
and no test needs an API key.
"""

from __future__ import annotations

import httpx
import pytest
from ega_providers import (
    COST_WARNING,
    PROVIDER_CATALOG,
    SUBSCRIPTION_NOTE,
    AnthropicProvider,
    CapabilityError,
    EchoSchemaProvider,
    GeminiProvider,
    HealthStatus,
    MalformedOutputError,
    NullProvider,
    OllamaProvider,
    OpenAICompatProvider,
    OpenAIProvider,
    ProviderAuthError,
    ProviderConfig,
    ProviderError,
    ProviderRegistry,
    ProviderTimeout,
    ProviderType,
    ProviderUnavailable,
    build_provider,
    get_provider,
    is_local_url,
    redact,
    resolve_api_key,
    truncate_snippet,
)
from ega_providers.base import (
    DEFAULT_TIMEOUT_S,
    MAX_RESPONSE_BYTES,
    GenerationSettings,
    fetch_json,
    raise_for_provider_status,
    response_json,
)
from ega_providers.registry import test_connection as check_connection
from pydantic import ValidationError

COST_WARNING_TEXT = "Provider API usage may cost money even though this app is free."
SUBSCRIPTION_NOTE_TEXT = "A ChatGPT/Claude consumer subscription is not automatically API access."


# --------------------------------------------------------------------------- #
# Static catalog (PRD FR-21)
# --------------------------------------------------------------------------- #


def test_catalog_covers_the_initial_adapter_set():
    """The six supported provider kinds are all advertised, and nothing else."""
    assert set(PROVIDER_CATALOG) == {
        "ollama",
        "openai_compatible",
        "openai",
        "anthropic",
        "gemini",
        "null",
    }


def test_catalog_carries_the_required_cost_and_subscription_warnings():
    """Every catalog entry shows the exact PRD-mandated warnings (FR-21)."""
    for provider_id, entry in PROVIDER_CATALOG.items():
        assert entry["cost_warning"] == COST_WARNING_TEXT, provider_id
        assert entry["subscription_note"] == SUBSCRIPTION_NOTE_TEXT, provider_id
    assert COST_WARNING == COST_WARNING_TEXT
    assert SUBSCRIPTION_NOTE == SUBSCRIPTION_NOTE_TEXT


def test_catalog_hides_the_test_only_adapter():
    """``EchoSchemaProvider`` must never be offered as a real option in the UI."""
    assert "test" not in PROVIDER_CATALOG
    assert "echo" not in PROVIDER_CATALOG


def test_catalog_cloud_entries_require_a_key_and_admit_their_cost():
    for provider_id in ("openai", "anthropic", "gemini"):
        entry = PROVIDER_CATALOG[provider_id]
        assert entry["requires_api_key"] is True
        assert entry["local"] is False


# --------------------------------------------------------------------------- #
# ProviderConfig validation
# --------------------------------------------------------------------------- #


def test_config_accepts_http_and_https_base_urls():
    assert ProviderConfig(id="a", type="ollama", base_url="http://localhost:11434").base_url
    assert ProviderConfig(id="b", type="openai", base_url="https://api.openai.com/v1").base_url


def test_config_treats_an_empty_base_url_as_unset():
    cfg = ProviderConfig(id="a", type="ollama", base_url="")
    assert cfg.base_url is None


@pytest.mark.parametrize(
    "bad_url",
    ["ftp://example.com", "file:///etc/passwd", "javascript:alert(1)", "example.com"],
)
def test_config_rejects_non_http_or_hostless_base_urls(bad_url: str):
    """Only http(s) endpoints with a host are allowed (SSRF surface)."""
    with pytest.raises(ValidationError):
        ProviderConfig(id="a", type="ollama", base_url=bad_url)


def test_config_rejects_a_secret_where_an_env_var_name_belongs():
    with pytest.raises(ValidationError):
        ProviderConfig(id="a", type="openai", api_key_env="sk-live-abc123")
    with pytest.raises(ValidationError):
        ProviderConfig(id="b", type="openai", api_key_env="MY KEY")
    assert ProviderConfig(id="c", type="openai", api_key_env="OPENAI_API_KEY").api_key_env


def test_config_never_stores_a_plaintext_credential_field():
    """There is no field for a raw key: only a name or an encrypted token."""
    assert "api_key" not in ProviderConfig.model_fields
    assert "api_key_env" in ProviderConfig.model_fields
    assert "api_key_encrypted" in ProviderConfig.model_fields


def test_config_repr_and_str_mask_the_encrypted_token():
    cfg = ProviderConfig(
        id="openai-prod",
        type="openai",
        model="gpt-4o-mini",
        api_key_encrypted="gAAAAABlSecretTokenValueDoNotLeak",
    )
    for rendered in (repr(cfg), str(cfg)):
        assert "gAAAAABlSecretTokenValueDoNotLeak" not in rendered
        assert "***REDACTED***" in rendered
        assert "gpt-4o-mini" in rendered  # non-secrets stay visible for debugging


def test_config_without_a_token_still_has_no_secret_in_repr():
    cfg = ProviderConfig(id="local", type="ollama", base_url="http://localhost:11434")
    assert "api_key_encrypted=None" in repr(cfg)


def test_legacy_type_spellings_coerce_to_supported_values():
    assert ProviderConfig(id="a", type="dummy").type is ProviderType.NULL
    assert ProviderConfig(id="b", type="none").type is ProviderType.NULL
    assert ProviderConfig(id="c", type="openai-compatible").type is ProviderType.OPENAI_COMPATIBLE
    assert ProviderConfig(id="d", type="ollama").type is ProviderType.OLLAMA


def test_unknown_provider_type_is_refused_with_the_supported_list():
    with pytest.raises(ValidationError, match="ollama"):
        ProviderConfig(id="a", type="made_up")


def test_sends_data_off_device_matches_the_privacy_contract():
    null_cfg = ProviderConfig(id="n", type="null")
    assert null_cfg.sends_data_off_device is False

    local_ollama = ProviderConfig(id="o", type="ollama", base_url="http://localhost:11434")
    assert local_ollama.sends_data_off_device is False

    remote_ollama = ProviderConfig(id="o2", type="ollama", base_url="https://ollama.example.com")
    assert remote_ollama.sends_data_off_device is True

    local_compat = ProviderConfig(
        id="c1", type="openai_compatible", base_url="http://127.0.0.1:11434/v1"
    )
    assert local_compat.sends_data_off_device is False

    for provider_type in ("openai", "anthropic", "gemini"):
        cfg = ProviderConfig(id=provider_type, type=provider_type)
        assert cfg.sends_data_off_device is True


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("http://localhost:11434", True),
        ("http://localhost.localdomain", True),
        ("http://service.localhost", True),
        ("http://127.0.0.1:8080", True),
        ("http://10.1.2.3", True),
        ("http://192.168.0.5/v1", True),
        ("http://169.254.0.1", True),
        ("https://api.openai.com/v1", False),
        ("http://my-server.local", False),  # hostname, not an IP literal: off-device
        ("file:///etc/passwd", False),
        ("", False),
        (None, False),
    ],
)
def test_is_local_url_is_conservative_and_dns_free(url, expected):
    assert is_local_url(url) is expected


# --------------------------------------------------------------------------- #
# Building providers
# --------------------------------------------------------------------------- #


def test_build_provider_returns_the_matching_adapter_class():
    assert isinstance(build_provider(ProviderConfig(id="n", type="null")), NullProvider)
    assert isinstance(
        build_provider(ProviderConfig(id="o", type="ollama", base_url="http://localhost:11434")),
        OllamaProvider,
    )
    assert isinstance(
        build_provider(
            ProviderConfig(id="c", type="openai_compatible", base_url="http://127.0.0.1:8000/v1")
        ),
        OpenAICompatProvider,
    )
    assert isinstance(
        build_provider(ProviderConfig(id="a", type="anthropic", api_key_env="X"), "sk-test"),
        AnthropicProvider,
    )
    assert isinstance(
        build_provider(ProviderConfig(id="g", type="gemini", api_key_env="Y"), "AIza-test"),
        GeminiProvider,
    )
    assert isinstance(
        build_provider(ProviderConfig(id="o", type="openai", api_key_env="Z"), "sk-test"),
        OpenAIProvider,
    )


def test_cloud_providers_refuse_to_build_without_a_key(monkeypatch):
    """No key means no call — adapters never fire unauthenticated requests."""
    monkeypatch.delenv("MISSING_KEY_VAR", raising=False)
    for provider_type in ("openai", "anthropic", "gemini"):
        cfg = ProviderConfig(id=provider_type, type=provider_type, api_key_env="MISSING_KEY_VAR")
        with pytest.raises(ProviderAuthError) as info:
            build_provider(cfg)
        assert info.value.provider == provider_type
        assert "MISSING_KEY_VAR" in info.value.safe_message


def test_openai_compatible_requires_a_base_url():
    cfg = ProviderConfig(id="c", type="openai_compatible")
    with pytest.raises(ProviderError, match="base_url is required"):
        build_provider(cfg)


def test_resolve_api_key_prefers_the_explicit_key_then_the_env_var():
    cfg = ProviderConfig(id="o", type="openai", api_key_env="MY_OPENAI_KEY")
    assert resolve_api_key(cfg, "explicit") == "explicit"
    assert resolve_api_key(cfg, None, env={"MY_OPENAI_KEY": "from-env"}) == "from-env"
    assert resolve_api_key(cfg, None, env={}) is None
    assert resolve_api_key(ProviderConfig(id="n", type="null")) is None


def test_get_provider_refuses_the_test_adapter_unless_allowed():
    with pytest.raises(ProviderError, match="allow_test=True"):
        get_provider("test")
    with pytest.raises(ProviderError, match="allow_test=True"):
        get_provider("echo")
    assert isinstance(get_provider("test", allow_test=True), EchoSchemaProvider)
    assert isinstance(get_provider("echo", allow_test=True), EchoSchemaProvider)


def test_get_provider_maps_legacy_aliases_to_the_null_adapter(monkeypatch):
    monkeypatch.delenv("DEFAULT_MODEL_PROVIDER", raising=False)
    assert isinstance(get_provider(None), NullProvider)
    assert isinstance(get_provider("none"), NullProvider)
    assert isinstance(get_provider(""), NullProvider)
    assert isinstance(get_provider(ProviderType.NULL), NullProvider)


def test_get_provider_reports_unknown_types_instead_of_guessing():
    with pytest.raises(ProviderError, match="Unsupported provider type"):
        get_provider("made-up")


def test_get_provider_never_changes_a_supplied_model_id(monkeypatch):
    monkeypatch.setenv("OLLAMA_DEFAULT_MODEL", "env-model-name")
    from_env = get_provider("ollama")
    assert from_env.model == "env-model-name"
    explicit = get_provider("ollama", model="totally-custom:tag")
    assert explicit.model == "totally-custom:tag"


def test_provider_registry_facade_is_backwards_compatible():
    """The workflow still calls ``ProviderRegistry.get_provider(type, model)``."""
    provider = ProviderRegistry.get_provider("ollama", "llama3.2:latest")
    assert isinstance(provider, OllamaProvider)
    assert provider.model == "llama3.2:latest"


# --------------------------------------------------------------------------- #
# Redaction and the error hierarchy (FR-21)
# --------------------------------------------------------------------------- #


def test_redact_removes_exact_secrets_and_key_shaped_patterns():
    assert redact("value=supersecret-42", ["supersecret-42"]) == "value=***REDACTED***"
    assert "sk-abc123456789" not in redact("key sk-abc123456789 leaked")
    assert "AIzaSyFakeKey00000000" not in redact("token AIzaSyFakeKey00000000 leaked")
    assert "hunter2secret" not in redact("Bearer hunter2secret", [])
    assert redact("nothing secret here") == "nothing secret here"


def test_truncate_snippet_redacts_first_and_respects_the_limit():
    long_text = "sk-abc123456789 " + ("x" * 500)
    snippet = truncate_snippet(long_text)
    assert "sk-abc123456789" not in snippet
    assert len(snippet) <= 200
    assert snippet.endswith("…")


@pytest.mark.parametrize(
    ("exc_type", "retryable"),
    [
        (ProviderError, False),
        (ProviderTimeout, True),
        (ProviderAuthError, False),
        (MalformedOutputError, True),
        (CapabilityError, False),
        (ProviderUnavailable, True),
    ],
)
def test_error_hierarchy_retryable_flags(exc_type, retryable: bool):
    exc = exc_type("something happened", provider="openai")
    assert exc.retryable is retryable
    assert exc.provider == "openai"
    assert exc.safe_message


def test_provider_error_never_carries_a_credential():
    secret = "sk-ant-TopSecretKeyValue"
    exc = ProviderAuthError(
        "anthropic rejected the key {secret}",
        provider="anthropic",
        secrets=[secret],
        snippet=f"body mentioning {secret} again",
    )
    for rendered in (str(exc), repr(exc), exc.safe_message):
        assert "TopSecretKeyValue" not in rendered
        assert "***REDACTED***" in rendered


def test_error_snippet_is_truncated_to_two_hundred_chars():
    exc = MalformedOutputError("bad output", provider="ollama", snippet="y" * 4000)
    assert len(exc.safe_message) <= 200 + len("Model returned output that could not be parsed as the required JSON. Snippet: ")
    assert "Snippet:" in exc.safe_message


# --------------------------------------------------------------------------- #
# HTTP hardening through fetch_json (MockTransport only)
# --------------------------------------------------------------------------- #


async def test_fetch_json_reports_auth_status_without_leaking_the_key():
    secret = "sk-literal-key-123456"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": f"bad key {secret}"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderAuthError) as info:
        await fetch_json(
            client,
            "https://api.openai.com/v1/chat/completions",
            provider="openai",
            headers={"authorization": f"Bearer {secret}"},
            secrets=[secret],
        )
    assert "key-123456" not in info.value.safe_message
    assert info.value.status_code == 401
    assert info.value.retryable is False
    await client.aclose()


@pytest.mark.parametrize(
    ("status", "exc_type", "retryable"),
    [
        (400, ProviderError, False),
        (403, ProviderAuthError, False),
        (404, ProviderUnavailable, False),
        (429, ProviderError, True),
        (500, ProviderUnavailable, True),
        (503, ProviderUnavailable, True),
    ],
)
async def test_fetch_json_maps_status_codes_to_the_hierarchy(status, exc_type, retryable):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(status, json={"e": "x"}))
    )
    with pytest.raises(exc_type) as info:
        await fetch_json(client, "http://svc.test/v1", provider="ollama")
    assert info.value.retryable is retryable
    assert info.value.status_code == status
    await client.aclose()


async def test_fetch_json_maps_transport_timeouts_onto_provider_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderTimeout) as info:
        await fetch_json(
            client,
            "http://localhost:11434/api/chat",
            provider="ollama",
            timeout_s=3.5,
            secrets=["sk-hidden-999"],
        )
    assert info.value.retryable is True
    assert "sk-hidden-999" not in info.value.safe_message
    await client.aclose()


async def test_fetch_json_maps_connection_errors_onto_provider_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderUnavailable):
        await fetch_json(client, "http://localhost:11434/api/tags", provider="ollama", method="GET")
    await client.aclose()


async def test_fetch_json_follows_redirects_up_to_the_cap():
    hops: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hops.append(request.url.path)
        return httpx.Response(302, headers={"location": "/next"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match="redirect limit"):
        await fetch_json(client, "http://svc.test/start", provider="ollama", method="GET")
    assert len(hops) == 6  # MAX_REDIRECTS (5) + the initial request
    await client.aclose()


async def test_fetch_json_follows_a_short_redirect_chain_to_success():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/start":
            return httpx.Response(307, headers={"location": "/step2"})
        if request.url.path == "/step2":
            return httpx.Response(301, headers={"location": "http://svc.test/final"})
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    response = await fetch_json(client, "http://svc.test/start", provider="ollama", method="GET")
    assert response.json() == {"ok": True}
    await client.aclose()


async def test_fetch_json_drops_credential_headers_on_a_cross_origin_redirect():
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "internal.test":
            return httpx.Response(302, headers={"location": "http://elsewhere.test/final"})
        captured.update({k.lower(): v for k, v in request.headers.items()})
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await fetch_json(
        client,
        "http://internal.test/v1/start",
        provider="openai",
        method="GET",
        headers={"authorization": "Bearer sk-must-not-leak", "x-api-key": "k-123"},
        secrets=["sk-must-not-leak"],
    )
    assert "authorization" not in captured
    assert "x-api-key" not in captured
    await client.aclose()


async def test_fetch_json_refuses_an_oversized_response_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1))

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderError, match="size cap"):
        await fetch_json(client, "http://svc.test/big", provider="ollama", method="GET")
    await client.aclose()


async def test_fetch_json_honours_the_call_timeout():
    seen: dict[str, float] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(request.extensions.get("timeout", {}))
        return httpx.Response(200, json={"ok": True})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    await fetch_json(client, "http://svc.test/v1", provider="ollama", timeout_s=12.5, method="GET")
    assert seen["read"] == 12.5
    assert seen["connect"] == 12.5
    await client.aclose()


async def test_fetch_json_returns_a_response_whose_body_response_json_rejects():
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="<html>hi</html>"))
    )
    response = await fetch_json(client, "http://svc.test/v1", provider="ollama", method="GET")
    assert response.status_code == 200
    with pytest.raises(ProviderError, match="non-JSON"):
        response_json(response, provider="ollama")
    await client.aclose()


def test_raise_for_provider_status_passes_2xx_and_3xx_through():
    for status in (200, 201, 204, 304):
        raise_for_provider_status(httpx.Response(status), provider="ollama")


def test_response_json_returns_decodable_payloads():
    response = httpx.Response(200, json={"models": []})
    assert response_json(response, provider="ollama") == {"models": []}


# --------------------------------------------------------------------------- #
# Health checks and capability metadata
# --------------------------------------------------------------------------- #


def _ollama_client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_ollama_health_check_is_ok_when_the_model_is_installed():
    client = _ollama_client(
        lambda request: httpx.Response(200, json={"models": [{"name": "llama3.2:latest"}]})
    )
    provider = OllamaProvider(model="llama3.2:latest", client=client)
    health = await provider.health_check()
    assert isinstance(health, HealthStatus)
    assert health.ok is True
    assert health.model_id == "llama3.2:latest"
    assert health.latency_ms >= 0
    await provider.aclose()


async def test_ollama_health_check_reports_a_missing_model_without_substituting_one():
    client = _ollama_client(lambda request: httpx.Response(200, json={"models": [{"name": "mistral"}]}))
    provider = OllamaProvider(model="llama3.2:latest", client=client)
    health = await provider.health_check()
    assert health.ok is False
    assert "not installed" in health.detail
    assert provider.model == "llama3.2:latest"  # never swapped for an installed model
    await provider.aclose()


async def test_ollama_health_check_reports_an_unreachable_server():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    client = _ollama_client(handler)
    provider = OllamaProvider(model="llama3.2:latest", client=client)
    health = await provider.health_check()
    assert health.ok is False
    assert health.detail
    await provider.aclose()


async def test_ollama_list_models_is_sorted_and_skips_blank_names():
    client = _ollama_client(
        lambda request: httpx.Response(
            200, json={"models": [{"name": "b:7b"}, {"name": "a:7b"}, {"name": ""}]}
        )
    )
    provider = OllamaProvider(client=client)
    assert await provider.list_models() == ["a:7b", "b:7b"]
    await provider.aclose()


async def test_ollama_health_check_when_the_server_has_no_models():
    client = _ollama_client(lambda request: httpx.Response(200, json={"models": []}))
    provider = OllamaProvider(model="llama3.2", client=client)
    health = await provider.health_check()
    assert health.ok is False
    assert "no models are installed" in health.detail
    await provider.aclose()


async def test_ollama_health_check_when_no_model_is_configured():
    client = _ollama_client(lambda request: httpx.Response(200, json={"models": [{"name": "x"}]}))
    provider = OllamaProvider(client=client)
    health = await provider.health_check()
    assert health.ok is False
    assert "no model is configured" in health.detail
    await provider.aclose()


def test_local_capabilities_never_claim_data_leaves_the_device():
    local = OllamaProvider(base_url="http://localhost:11434", model="llama3.2")
    caps = local.capabilities()
    assert caps.provider == "ollama"
    assert caps.model_id == "llama3.2"
    assert caps.structured_output is True
    assert caps.sends_data_off_device is False

    remote = OllamaProvider(base_url="https://ollama.example.com", model="llama3.2")
    assert remote.capabilities().sends_data_off_device is True


def test_null_provider_capabilities_advertise_no_generation():
    caps = NullProvider().capabilities()
    assert caps.provider == "null"
    assert caps.structured_output is False
    assert caps.tool_calls is False
    assert caps.sends_data_off_device is False
    assert any("deterministic-only" in note.lower() for note in caps.notes)


async def test_null_provider_health_check_declares_deterministic_only_mode():
    health = await NullProvider().health_check()
    assert health.ok is False
    assert "deterministic-only mode" in health.detail


async def test_null_provider_never_generates_content():
    """FR-22: a stage without a model fails loudly instead of inventing text."""
    provider = NullProvider()
    settings = GenerationSettings(model="")
    with pytest.raises(CapabilityError):
        await provider.generate_structured(
            schema={"type": "object"}, messages=[{"role": "user", "content": "hi"}], settings=settings
        )
    with pytest.raises(CapabilityError):
        await provider.generate_text(messages=[{"role": "user", "content": "hi"}], settings=settings)
    with pytest.raises(CapabilityError):
        await provider.embed(["hello"], settings)


def test_provider_repr_never_contains_a_configured_api_key():
    key = "sk-ant-VERYSECRETVALUE123"
    provider = AnthropicProvider(api_key=key, model="claude-3-5-sonnet-20241022")
    for rendered in (repr(provider), str(provider)):
        assert "VERYSECRETVALUE123" not in rendered
    assert provider.capabilities().provider == "anthropic"


def test_gemini_and_openai_reprs_are_also_redacted():
    gemini = GeminiProvider(api_key="AIzaSyVerySecretKeyValue", model="gemini-2.0-flash")
    openai = OpenAIProvider(api_key="sk-VerySecretOpenAIKey", model="gpt-4o-mini")
    assert "AIzaSyVerySecretKeyValue" not in repr(gemini)
    assert "sk-VerySecretOpenAIKey" not in repr(openai)


# --------------------------------------------------------------------------- #
# Connection testing (UI helper)
# --------------------------------------------------------------------------- #


async def test_connection_returns_not_ok_for_a_configuration_that_cannot_build():
    cfg = ProviderConfig(id="openai-prod", type="openai", api_key_env="NOT_SET_ANYWHERE")
    ok, latency, detail = await check_connection(cfg)
    assert ok is False
    assert latency is None
    assert "NOT_SET_ANYWHERE" in detail


async def test_connection_never_raises_for_an_invalid_url():
    cfg = ProviderConfig.model_construct(id="bad", type=ProviderType.OLLAMA, base_url="nonsense")
    ok, latency, detail = await check_connection(cfg)
    assert ok is False
    assert isinstance(detail, str)


async def test_connection_for_the_null_adapter_reports_deterministic_only():
    ok, latency, detail = await check_connection(ProviderConfig(id="n", type="null"))
    assert ok is False
    assert "deterministic-only mode" in detail
    assert latency is not None and latency >= 0


def test_default_timeout_constant_matches_the_contract():
    assert DEFAULT_TIMEOUT_S == 60.0
    assert GenerationSettings(model="m").timeout_s == 60.0
