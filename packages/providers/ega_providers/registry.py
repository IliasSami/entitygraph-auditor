"""Provider registry, configuration model and static UI catalog (PRD FR-21/FR-22).

* :class:`ProviderType` — the six supported provider kinds.
* :class:`ProviderConfig` — validated, credential-free configuration model.
  Secrets live only as an *environment-variable name* (``api_key_env``) or an
  *encrypted token* (``api_key_encrypted``); there is no plaintext key field
  and no default credentials. ``__repr__``/``__str__`` mask the token.
* :func:`build_provider` — config → adapter; cloud providers without a key
  raise :class:`ProviderAuthError` (no silent unauthenticated calls).
* :func:`get_provider` — lightweight factory (env-var aware); ``"test"`` is
  refused unless ``allow_test=True`` (test-only adapter stays hidden).
* :func:`test_connection` — ``(ok, latency_ms, detail)`` for the UI.
* :data:`PROVIDER_CATALOG` — static metadata for the Model Providers page,
  including the cost/subscription warnings PRD FR-21 requires.
"""

from __future__ import annotations

import os
import re
from enum import Enum
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator

from ega_providers.anthropic import AnthropicProvider
from ega_providers.base import DEFAULT_TIMEOUT_S, ModelProvider, is_local_url
from ega_providers.deterministic import EchoSchemaProvider, NullProvider
from ega_providers.errors import ProviderAuthError, ProviderError, redact, truncate_snippet
from ega_providers.gemini import GeminiProvider
from ega_providers.ollama import OllamaProvider
from ega_providers.openai import OpenAIProvider
from ega_providers.openai_compat import OpenAICompatProvider

#: Required cost warning (FR-21) — shown for every provider in the UI.
COST_WARNING: str = "Provider API usage may cost money even though this app is free."

#: Required subscription caveat (FR-21).
SUBSCRIPTION_NOTE: str = "A ChatGPT/Claude consumer subscription is not automatically API access."


class ProviderType(str, Enum):
    """Supported provider kinds (FR-21 initial adapter set)."""

    OLLAMA = "ollama"
    OPENAI_COMPATIBLE = "openai_compatible"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    NULL = "null"


#: Accepted legacy/variant spellings mapped onto :class:`ProviderType` values.
_TYPE_ALIASES: dict[str, str] = {
    "": "null",
    "none": "null",
    "dummy": "null",  # legacy default → honest deterministic-only mode
    "dummy_deterministic": "null",
    "deterministic_baseline": "null",
    "deterministic": "null",
    "openai-compatible": "openai_compatible",
    "openai_compat": "openai_compatible",
    "google": "gemini",
    "google_gemini": "gemini",
}


def _normalize_type(value: Any) -> Any:
    """Coerce legacy strings into :class:`ProviderType` values (before-validator)."""
    if isinstance(value, ProviderType):
        return value
    if isinstance(value, str):
        key = _TYPE_ALIASES.get(value.strip().lower(), value.strip().lower())
        try:
            return ProviderType(key)
        except ValueError as exc:
            expected = ", ".join(member.value for member in ProviderType)
            raise ValueError(
                f"Unknown provider type {value!r}; expected one of: {expected}"
            ) from exc
    return value


class ProviderConfig(BaseModel):
    """Stored provider configuration without any plaintext credential.

    ``api_key_env`` names an environment variable; ``api_key_encrypted`` is an
    opaque Fernet token (see :mod:`ega_providers.crypto`). Neither ever
    appears unmasked in ``repr()``/``str()``.
    """

    id: str
    type: ProviderType
    label: str = ""
    base_url: str | None = None
    model: str = ""
    api_key_env: str | None = None
    api_key_encrypted: str | None = None
    timeout_s: float = Field(default=60.0, gt=0)
    max_tokens: int = Field(default=2048, gt=0)
    temperature: float = 0.0
    extra_headers: dict[str, str] = Field(default_factory=dict)
    notes: str = ""

    @field_validator("type", mode="before")
    @classmethod
    def _coerce_type(cls, value: Any) -> Any:
        return _normalize_type(value)

    @field_validator("base_url")
    @classmethod
    def _http_scheme_only(cls, value: str | None) -> str | None:
        """Only http(s) endpoints are allowed as provider base URLs."""
        if value is None or value == "":
            return None
        parts = urlsplit(value)
        if parts.scheme not in ("http", "https") or not parts.netloc:
            raise ValueError("base_url must be an http(s) URL with a host")
        return value

    @field_validator("api_key_env")
    @classmethod
    def _env_name_not_value(cls, value: str | None) -> str | None:
        """``api_key_env`` holds a variable NAME — never a secret value."""
        if value is None or value == "":
            return None
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError(
                "api_key_env must be an environment variable NAME, not a credential"
            )
        return value

    @property
    def sends_data_off_device(self) -> bool:
        """Would a call through this config leave this machine? (FR-21)

        * ``null`` — never.
        * ``ollama`` / ``openai_compatible`` — only when the base URL is not
          loopback/private (conservative: non-IP hostnames count as off-device).
        * cloud providers — always.
        """
        if self.type is ProviderType.NULL:
            return False
        if self.type is ProviderType.OLLAMA:
            return not is_local_url(self.base_url or OllamaProvider.DEFAULT_BASE_URL)
        if self.type is ProviderType.OPENAI_COMPATIBLE:
            return not is_local_url(self.base_url)
        return True

    def __repr__(self) -> str:
        """Credential-free representation — safe for logs and audit trails."""
        masked = "***REDACTED***" if self.api_key_encrypted else None
        return (
            f"{type(self).__name__}(id={self.id!r}, type={self.type.value!r}, "
            f"label={self.label!r}, base_url={self.base_url!r}, model={self.model!r}, "
            f"api_key_env={self.api_key_env!r}, api_key_encrypted={masked!r}, "
            f"timeout_s={self.timeout_s!r}, max_tokens={self.max_tokens!r}, "
            f"temperature={self.temperature!r}, "
            f"extra_headers={sorted(self.extra_headers)!r}, notes={self.notes!r})"
        )

    __str__ = __repr__


#: Static catalog backing the Model Providers UI (FR-21). Test-only adapters
#: (``EchoSchemaProvider``) are deliberately absent.
PROVIDER_CATALOG: dict[str, dict[str, Any]] = {
    "ollama": {
        "id": "ollama",
        "label": "Ollama (self-hosted, local)",
        "docs_url": "https://github.com/ollama/ollama/blob/main/docs/api.md",
        "requires_api_key": False,
        "local": True,
        "structured_output": True,
        "description": "Run open-weights models on your own machine through an Ollama server.",
        "default_base_url": "http://localhost:11434",
        "default_model": "llama3.2:latest",
        "cost_warning": COST_WARNING,
        "subscription_note": SUBSCRIPTION_NOTE,
        "local_note": "Local inference has no per-call API cost.",
    },
    "openai_compatible": {
        "id": "openai_compatible",
        "label": "OpenAI-compatible endpoint",
        "docs_url": "https://platform.openai.com/docs/api-reference/chat",
        "requires_api_key": False,
        "local": False,
        "structured_output": True,
        "description": (
            "Any OpenAI-style /chat/completions endpoint (vLLM, LM Studio, llama.cpp, "
            "Ollama OpenAI mode). API key optional; locality depends on base_url — "
            "loopback endpoints keep text on this machine."
        ),
        "default_base_url": None,
        "default_model": "",
        "cost_warning": COST_WARNING,
        "subscription_note": SUBSCRIPTION_NOTE,
    },
    "openai": {
        "id": "openai",
        "label": "OpenAI API (bring-your-own key)",
        "docs_url": "https://platform.openai.com/docs/api-reference/chat",
        "requires_api_key": True,
        "local": False,
        "structured_output": True,
        "description": "Official OpenAI chat-completions API with strict JSON-schema output.",
        "default_base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "cost_warning": COST_WARNING,
        "subscription_note": SUBSCRIPTION_NOTE,
    },
    "anthropic": {
        "id": "anthropic",
        "label": "Anthropic API (bring-your-own key)",
        "docs_url": "https://docs.anthropic.com/en/api/messages",
        "requires_api_key": True,
        "local": False,
        "structured_output": True,
        "description": "Official Anthropic Messages API; structured output via a forced tool.",
        "default_base_url": "https://api.anthropic.com",
        "default_model": "claude-3-5-sonnet-20241022",
        "cost_warning": COST_WARNING,
        "subscription_note": SUBSCRIPTION_NOTE,
    },
    "gemini": {
        "id": "gemini",
        "label": "Google Gemini API (bring-your-own key)",
        "docs_url": "https://ai.google.dev/api/generate-content",
        "requires_api_key": True,
        "local": False,
        "structured_output": True,
        "description": "Official Gemini generateContent API with responseSchema output.",
        "default_base_url": "https://generativelanguage.googleapis.com",
        "default_model": "gemini-2.0-flash",
        "cost_warning": COST_WARNING,
        "subscription_note": SUBSCRIPTION_NOTE,
    },
    "null": {
        "id": "null",
        "label": "Deterministic-only (no model)",
        "docs_url": None,
        "requires_api_key": False,
        "local": True,
        "structured_output": False,
        "description": (
            "Offline structural analysis with no model; semantic stages are skipped "
            "and reported as not_assessed (PRD FR-22)."
        ),
        "default_base_url": None,
        "default_model": "",
        "cost_warning": COST_WARNING,
        "subscription_note": SUBSCRIPTION_NOTE,
        "local_note": "No inference and no data leaves this machine.",
    },
}


def resolve_api_key(
    config: ProviderConfig,
    decrypted_key: str | None = None,
    env: dict[str, str] | None = None,
) -> str | None:
    """Resolve the credential: explicit decrypted key, then ``api_key_env``.

    Returns ``None`` when neither is available — no credential guessing and
    no logging of any value.
    """
    if decrypted_key:
        return decrypted_key
    if config.api_key_env:
        environ = os.environ if env is None else env
        value = environ.get(config.api_key_env)
        if value:
            return value
    return None


def _require_key(config: ProviderConfig, key: str | None, provider_name: str) -> str:
    """Cloud providers refuse to build without a key (FR-21 BYOK honesty)."""
    if not key:
        hint = (
            f"Set {config.api_key_env}."
            if config.api_key_env
            else "Provide an API key or set api_key_env."
        )
        raise ProviderAuthError(
            f"No API key configured for provider '{provider_name}'. {hint}",
            provider=provider_name,
        )
    return key


def build_provider(config: ProviderConfig, decrypted_key: str | None = None) -> ModelProvider:
    """Instantiate the adapter described by ``config``.

    Args:
        config: Validated provider configuration (no plaintext secrets).
        decrypted_key: Decrypted API key from storage
            (:func:`ega_providers.crypto.decrypt_secret`) or a key supplied
            for a one-off connection test.

    Raises:
        ProviderAuthError: cloud provider without any key.
        ProviderError: configuration that cannot be built (e.g. missing
            ``base_url`` for ``openai_compatible``).
    """
    key = resolve_api_key(config, decrypted_key)
    headers = dict(config.extra_headers)
    timeout = float(config.timeout_s)

    if config.type is ProviderType.NULL:
        return NullProvider(default_timeout_s=timeout)
    if config.type is ProviderType.OLLAMA:
        return OllamaProvider(
            base_url=config.base_url,
            model=config.model,
            extra_headers=headers,
            default_timeout_s=timeout,
        )
    if config.type is ProviderType.OPENAI_COMPATIBLE:
        if not config.base_url:
            raise ProviderError(
                "base_url is required for the openai_compatible provider "
                "(e.g. http://localhost:11434/v1).",
                provider="openai_compatible",
                retryable=False,
            )
        return OpenAICompatProvider(
            base_url=config.base_url,
            model=config.model,
            api_key=key,
            extra_headers=headers,
            default_timeout_s=timeout,
        )
    if config.type is ProviderType.OPENAI:
        _require_key(config, key, "openai")
        return OpenAIProvider(
            api_key=key,
            base_url=config.base_url or "https://api.openai.com/v1",
            model=config.model,
            extra_headers=headers,
            default_timeout_s=timeout,
        )
    if config.type is ProviderType.ANTHROPIC:
        _require_key(config, key, "anthropic")
        return AnthropicProvider(
            api_key=key,
            base_url=config.base_url or "https://api.anthropic.com",
            model=config.model,
            extra_headers=headers,
            default_timeout_s=timeout,
        )
    if config.type is ProviderType.GEMINI:
        _require_key(config, key, "gemini")
        return GeminiProvider(
            api_key=key,
            base_url=config.base_url,
            model=config.model,
            extra_headers=headers,
            default_timeout_s=timeout,
        )
    raise ProviderError(  # pragma: no cover - enum is exhaustive
        f"Unsupported provider type '{config.type.value}'.",
        provider=str(config.type.value),
        retryable=False,
    )


#: Environment variable consulted for each provider's model ID by :func:`get_provider`.
_MODEL_ENV: dict[ProviderType, str] = {
    ProviderType.OLLAMA: "OLLAMA_DEFAULT_MODEL",
    ProviderType.OPENAI: "OPENAI_MODEL",
    ProviderType.OPENAI_COMPATIBLE: "OPENAI_COMPATIBLE_MODEL",
    ProviderType.ANTHROPIC: "ANTHROPIC_MODEL",
    ProviderType.GEMINI: "GEMINI_MODEL",
}

#: Environment variable consulted for each provider's base URL.
_BASE_URL_ENV: dict[ProviderType, str] = {
    ProviderType.OLLAMA: "OLLAMA_BASE_URL",
    ProviderType.OPENAI: "OPENAI_BASE_URL",
}

#: Environment variable holding each cloud provider's API key name.
_KEY_ENV: dict[ProviderType, str] = {
    ProviderType.OPENAI: "OPENAI_API_KEY",
    ProviderType.ANTHROPIC: "ANTHROPIC_API_KEY",
    ProviderType.GEMINI: "GEMINI_API_KEY",
}


def get_provider(
    provider_type: str | ProviderType | None = None,
    *,
    model: str | None = None,
    model_name: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    max_tokens: int = 2048,
    temperature: float = 0.0,
    allow_test: bool = False,
) -> ModelProvider:
    """Create an adapter from simple arguments (env-var aware).

    ``provider_type`` accepts the six :class:`ProviderType` values plus the
    legacy aliases (``"dummy"`` → ``null``). ``"test"``/``"echo"`` returns the
    test-only :class:`EchoSchemaProvider` **only** when ``allow_test=True``.

    The model ID is used verbatim when given; otherwise the provider's
    conventional environment variable supplies it.
    """
    raw = provider_type if provider_type is not None else os.getenv("DEFAULT_MODEL_PROVIDER", "null")
    if isinstance(raw, ProviderType):
        # An enum member stringifies to "ProviderType.NULL", not "null" — use its value.
        raw_str = key_text = raw.value
    else:
        raw_str = str(raw).strip().lower()
        if raw_str in ("dummy", "dummy_deterministic", "deterministic_baseline", "deterministic"):
            from ega_providers.dummy import DummyDeterministicProvider

            return DummyDeterministicProvider()
        key_text = _TYPE_ALIASES.get(raw_str, raw_str)

    if key_text in ("test", "echo", "echoschema"):
        if allow_test:
            return EchoSchemaProvider(model=model or model_name or "echo-schema-test")
        raise ProviderError(
            "Provider type 'test' is reserved for tests; pass allow_test=True to use it.",
            provider="test",
            retryable=False,
        )


    try:
        ptype = _normalize_type(key_text)
    except ValueError as exc:
        raise ProviderError(
            f"Unsupported provider type {provider_type!r}. "
            f"Expected one of: {', '.join(member.value for member in ProviderType)}.",
            provider=str(provider_type),
            retryable=False,
        ) from exc
    if not isinstance(ptype, ProviderType):  # pragma: no cover - normalizer is exhaustive
        raise ProviderError(
            f"Unsupported provider type {provider_type!r}.",
            provider=str(provider_type),
            retryable=False,
        )

    resolved_base_url = base_url
    if resolved_base_url is None:
        base_env = _BASE_URL_ENV.get(ptype)
        resolved_base_url = os.getenv(base_env) if base_env else None

    resolved_model = model or model_name or ""
    if not resolved_model:
        model_env = _MODEL_ENV.get(ptype)
        resolved_model = os.getenv(model_env, "") if model_env else ""

    key_env = None if api_key else _KEY_ENV.get(ptype)

    config = ProviderConfig(
        id=f"adhoc-{ptype.value}",
        type=ptype,
        label=ptype.value,
        base_url=resolved_base_url,
        model=resolved_model,
        api_key_env=key_env,
        timeout_s=float(timeout_s),
        max_tokens=int(max_tokens),
        temperature=float(temperature),
    )
    return build_provider(config, api_key)


class ProviderRegistry:
    """Backward-compatible facade kept for existing importers.

    New code should use :func:`get_provider` / :func:`build_provider`.
    """

    @classmethod
    def get_provider(
        cls,
        provider_type: str | ProviderType | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        **kwargs: Any,
    ) -> ModelProvider:
        """Adapter factory mirroring the module-level :func:`get_provider`."""
        return get_provider(
            provider_type,
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )


async def test_connection(
    config: ProviderConfig, decrypted_key: str | None = None
) -> tuple[bool, float | None, str]:
    """Test a provider configuration: ``(ok, latency_ms, detail)``.

    Used by ``POST /models/test-connection``. Never raises and never returns
    credentials in ``detail`` (all messages pass through the redacting
    exception hierarchy).
    """
    try:
        provider = build_provider(config, decrypted_key)
    except ProviderError as exc:
        return False, None, exc.safe_message
    except Exception as exc:  # validation/URL problems — redacted
        return False, None, truncate_snippet(redact(str(exc)))
    try:
        health = await provider.health_check()
    except ProviderError as exc:
        return False, None, exc.safe_message
    except Exception as exc:  # pragma: no cover - defensive
        return False, None, truncate_snippet(redact(str(exc)))
    finally:
        await provider.aclose()
    return health.ok, health.latency_ms, health.detail


test_connection.__test__ = False

