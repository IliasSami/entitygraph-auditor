"""Provider error hierarchy with guaranteed secret redaction (PRD FR-21, §23).

Every exception in this module carries three things:

* ``provider``   — which adapter raised it;
* ``retryable``  — whether a retry (with the same model ID) may succeed;
* ``safe_message`` — a human-readable message that NEVER contains API keys.

``redact()`` is applied to every message at construction time, both to any
explicit ``secrets`` passed by the adapter (the configured API key) and to
common key patterns (``sk-…``, ``AIza…``, ``Bearer …``).  HTTP headers are
never included in exception messages by construction: adapters pass only the
response *body* snippet, which is redacted and truncated by the helpers here.

A failed call always raises; no adapter may fabricate content on failure
(PRD §13.3).  The workflow marks the stage skipped/failed instead.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

#: Maximum snippet length embedded in an error message (chars).
MAX_SNIPPET_CHARS = 200

_REDACTED = "***REDACTED***"

#: Patterns for common credential shapes, scrubbed from every message.
_KEY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{8,}"),  # Anthropic
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),  # OpenAI-style
    re.compile(r"AIza[0-9A-Za-z_\-]{10,}"),  # Google API keys
    re.compile(r"hg_[A-Za-z0-9_\-]{8,}"),  # generic
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=\-]+", re.IGNORECASE),
    re.compile(r"(x-api-key|api[-_]?key|authorization)\s*[:=]\s*\"?[^\s\"',;&]+", re.IGNORECASE),
)


def redact(text: str, secrets: Iterable[str] = ()) -> str:
    """Return ``text`` with known secret values and key-shaped patterns removed.

    This helper is used by *every* exception in this module and by adapter
    code before a response snippet is attached to an error.  It never logs
    or returns the plaintext secret values it was given.

    Args:
        text: Arbitrary text (error message, response-body snippet).
        secrets: Exact secret strings (e.g. the configured API key) to mask.

    Returns:
        A string safe to log or show in the UI.
    """
    out = text
    for secret in secrets:
        if secret:
            out = out.replace(secret, _REDACTED)
    for pattern in _KEY_PATTERNS:
        out = pattern.sub(_REDACTED, out)
    return out


def truncate_snippet(text: str, *, limit: int = MAX_SNIPPET_CHARS, secrets: Iterable[str] = ()) -> str:
    """Redact then truncate ``text`` to ``limit`` chars, appending an ellipsis."""
    cleaned = redact(text, secrets)
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


class ProviderError(Exception):
    """Base class for all model-provider failures.

    Attributes:
        provider: Adapter name (e.g. ``"ollama"``).
        retryable: ``True`` when retrying the identical request may succeed.
        safe_message: Redacted, loggable description of the failure.
        status_code: Optional HTTP status code, when the failure came from
            an HTTP response.
    """

    default_message: str = "Model provider call failed."
    default_retryable: bool = False

    def __init__(
        self,
        safe_message: str | None = None,
        *,
        provider: str = "unknown",
        retryable: bool | None = None,
        secrets: Iterable[str] = (),
        status_code: int | None = None,
        snippet: str | None = None,
    ) -> None:
        self.provider = provider
        self.retryable = self.default_retryable if retryable is None else retryable
        self.status_code = status_code
        self._secrets: tuple[str, ...] = tuple(s for s in secrets if s)
        message = redact(safe_message or self.default_message, self._secrets)
        if snippet:
            message = f"{message} Snippet: {truncate_snippet(snippet, secrets=self._secrets)}"
        self.safe_message = message
        super().__init__(message)

    def __repr__(self) -> str:
        """Redacted representation — never contains secrets or headers."""
        return (
            f"{type(self).__name__}(provider={self.provider!r}, "
            f"retryable={self.retryable}, safe_message={self.safe_message!r})"
        )


class ProviderTimeout(ProviderError):
    """The provider did not answer within the configured timeout."""

    default_message = "Provider request timed out."
    default_retryable = True


class ProviderAuthError(ProviderError):
    """Missing or rejected credentials (401/403). Never carries the key."""

    default_message = "Provider authentication failed. Check the configured API key."
    default_retryable = False


class MalformedOutputError(ProviderError):
    """The model answered, but the output is not usable JSON for the schema.

    Retryable by design: PRD §23 allows one repair call per node for
    malformed output.
    """

    default_message = "Model returned output that could not be parsed as the required JSON."
    default_retryable = True


class CapabilityError(ProviderError):
    """The selected provider/model cannot perform the requested operation."""

    default_message = "The selected provider does not support this capability."
    default_retryable = False


class ProviderUnavailable(ProviderError):
    """The provider is unreachable, not ready, or answered 5xx/404."""

    default_message = "Provider is unreachable or not ready."
    default_retryable = True
