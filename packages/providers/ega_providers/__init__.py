"""Model provider adapters for EntityGraph Auditor (PRD §13.3, FR-21/FR-22).

Public surface:

* :class:`~ega_providers.base.ModelProvider` — the adapter contract;
  :class:`~ega_providers.base.GenerationSettings`,
  :class:`~ega_providers.base.ProviderCapabilities`,
  :class:`~ega_providers.base.HealthStatus` and
  :func:`~ega_providers.base.parse_structured`.
* Adapters: :class:`~ega_providers.ollama.OllamaProvider`,
  :class:`~ega_providers.openai_compat.OpenAICompatProvider`,
  :class:`~ega_providers.openai.OpenAIProvider`,
  :class:`~ega_providers.anthropic.AnthropicProvider`,
  :class:`~ega_providers.gemini.GeminiProvider`,
  :class:`~ega_providers.deterministic.NullProvider` (deterministic-only)
  and the test-only :class:`~ega_providers.deterministic.EchoSchemaProvider`.
* Registry: :func:`~ega_providers.registry.build_provider`,
  :func:`~ega_providers.registry.get_provider`,
  :func:`~ega_providers.registry.test_connection`,
  :class:`~ega_providers.registry.ProviderConfig`,
  :class:`~ega_providers.registry.ProviderType`,
  :data:`~ega_providers.registry.PROVIDER_CATALOG`.
* Crypto: :func:`~ega_providers.crypto.derive_key`,
  :func:`~ega_providers.crypto.encrypt_secret`,
  :func:`~ega_providers.crypto.decrypt_secret`.

Hard rules (FR-21/§13.3): a failed call raises, model IDs are never silently
changed, data never goes to an unselected provider, and API keys never appear
in reprs, logs, or error messages.
"""

from __future__ import annotations

from ega_providers.anthropic import AnthropicProvider
from ega_providers.base import (
    DEFAULT_TIMEOUT_S,
    MAX_REDIRECTS,
    MAX_RESPONSE_BYTES,
    GenerationSettings,
    HealthStatus,
    ModelProvider,
    ProviderCapabilities,
    StructuredResult,
    is_local_url,
    parse_structured,
    split_system,
    validate_required,
)
from ega_providers.crypto import decrypt_secret, derive_key, encrypt_secret
from ega_providers.deterministic import EchoSchemaProvider, NullProvider
from ega_providers.errors import (
    CapabilityError,
    MalformedOutputError,
    ProviderAuthError,
    ProviderError,
    ProviderTimeout,
    ProviderUnavailable,
    redact,
    truncate_snippet,
)
from ega_providers.gemini import GeminiProvider, convert_json_schema
from ega_providers.ollama import OllamaProvider
from ega_providers.openai import OpenAIProvider
from ega_providers.openai_compat import OpenAICompatProvider
from ega_providers.registry import (
    COST_WARNING,
    PROVIDER_CATALOG,
    SUBSCRIPTION_NOTE,
    ProviderConfig,
    ProviderRegistry,
    ProviderType,
    build_provider,
    get_provider,
    resolve_api_key,
    test_connection,
)

__all__ = [
    "COST_WARNING",
    "DEFAULT_TIMEOUT_S",
    "MAX_REDIRECTS",
    "MAX_RESPONSE_BYTES",
    "PROVIDER_CATALOG",
    "SUBSCRIPTION_NOTE",
    "AnthropicProvider",
    "CapabilityError",
    "EchoSchemaProvider",
    "GeminiProvider",
    "GenerationSettings",
    "HealthStatus",
    "MalformedOutputError",
    "ModelProvider",
    "NullProvider",
    "OllamaProvider",
    "OpenAICompatProvider",
    "OpenAIProvider",
    "ProviderAuthError",
    "ProviderCapabilities",
    "ProviderConfig",
    "ProviderError",
    "ProviderRegistry",
    "ProviderTimeout",
    "ProviderType",
    "ProviderUnavailable",
    "StructuredResult",
    "build_provider",
    "convert_json_schema",
    "decrypt_secret",
    "derive_key",
    "encrypt_secret",
    "get_provider",
    "is_local_url",
    "parse_structured",
    "redact",
    "resolve_api_key",
    "split_system",
    "test_connection",
    "truncate_snippet",
    "validate_required",
]
