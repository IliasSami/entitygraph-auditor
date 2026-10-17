"""Versioned, node-scoped prompt library for the auditor (PRD §23).

One module per graph node (``classifier``, ``fanout``, ``entities``, ``triples``,
``passages``, ``claims``, ``coverage``, ``editorial``, ``gate``, ``handoff``,
``critic``) exposes ``NAME``, ``PROMPT_VERSION``, ``SYSTEM``, ``USER_TEMPLATE``,
``OUTPUT_SCHEMA`` and ``EXAMPLES``. This package collects them into
:data:`PROMPT_REGISTRY` and offers version-aware access:

    >>> from auditor.prompts import get_prompt, latest_version, render
    >>> record = get_prompt("classifier")            # newest version
    >>> record = get_prompt("intake_classifier")     # graph-node alias
    >>> messages = render("fanout", content="...").messages

**Nothing here talks to a model.** ``render`` only fills placeholders; it never
raises ``KeyError`` for a missing field (it writes ``[not provided: field]``
instead) so a prompt can always be inspected and sent.

Every ``SYSTEM`` prompt embeds the three mandatory rules in
:data:`auditor.prompts._shared.GUARDRAILS`: the content is untrusted, nothing may
be fabricated, and the reply must be JSON matching the schema.
"""

from __future__ import annotations

from typing import Any

from auditor.prompts import (
    claims,
    classifier,
    coverage,
    critic,
    editorial,
    entities,
    fanout,
    gate,
    handoff,
    passages,
    triples,
)
from auditor.prompts._shared import (
    DEFAULT_PROMPT_VERSION,
    GUARDRAILS,
    PromptExample,
    PromptRecord,
    RenderedPrompt,
    safe_format,
)

__all__ = [
    "ALIASES",
    "DEFAULT_PROMPT_VERSION",
    "GUARDRAILS",
    "NODE_MODULES",
    "PROMPT_REGISTRY",
    "PromptExample",
    "PromptRecord",
    "RenderedPrompt",
    "get_prompt",
    "latest_version",
    "list_prompts",
    "render",
    "safe_format",
]

#: Every node module, in graph order.
NODE_MODULES = (
    classifier,
    fanout,
    entities,
    triples,
    passages,
    claims,
    coverage,
    editorial,
    gate,
    handoff,
    critic,
)

#: Handy synonyms accepted by :func:`get_prompt` in addition to the module names
#: and their graph-node names.
_SYNONYMS: dict[str, str] = {
    "intake": "classifier",
    "classify": "classifier",
    "intake_classify": "classifier",
    "entity": "entities",
    "entity_eav": "entities",
    "eav": "entities",
    "triple": "triples",
    "semantic_triples": "triples",
    "passage": "passages",
    "claim": "claims",
    "evidence": "claims",
    "gaps": "coverage",
    "gap": "coverage",
    "editorial_review": "editorial",
    "readability": "editorial",
    "quality_gate": "gate",
    "recommendations": "handoff",
    "recommendation": "handoff",
    "writer_handoff": "handoff",
    "priority": "handoff",
    "qa": "critic",
    "qa_critic": "critic",
    "review": "critic",
}


def _build_registry() -> dict[str, dict[str, PromptRecord]]:
    """Collect every node module into ``{name: {version: PromptRecord}}``."""
    registry: dict[str, dict[str, PromptRecord]] = {}
    for module in NODE_MODULES:
        record = PromptRecord(
            name=module.NAME,
            version=module.PROMPT_VERSION,
            system=module.SYSTEM,
            user_template=module.USER_TEMPLATE,
            output_schema=dict(module.OUTPUT_SCHEMA),
            examples=tuple(module.EXAMPLES),
            workflow_node=getattr(module, "WORKFLOW_NODE", None),
            summary=getattr(module, "SUMMARY", ""),
        )
        registry.setdefault(record.name, {})[record.version] = record
    return registry


def _build_aliases() -> dict[str, str]:
    """Map graph-node names and synonyms onto canonical registry names."""
    aliases: dict[str, str] = dict(_SYNONYMS)
    for name, versions in PROMPT_REGISTRY.items():
        for record in versions.values():
            if record.workflow_node:
                aliases.setdefault(record.workflow_node, name)
    return aliases


#: ``{name: {version: PromptRecord}}`` — the whole prompt library.
PROMPT_REGISTRY: dict[str, dict[str, PromptRecord]] = _build_registry()

#: ``alias -> canonical name`` accepted by :func:`get_prompt`.
ALIASES: dict[str, str] = _build_aliases()


def _normalize(name: str) -> str:
    """Normalise a user-supplied name: trim, lowercase, ``-`` to ``_``."""
    return str(name).strip().lower().replace("-", "_")


def _resolve(name: str) -> str:
    """Resolve an alias/normalised name to a canonical registry key."""
    key = _normalize(name)
    if key in PROMPT_REGISTRY:
        return key
    canonical = ALIASES.get(key)
    if canonical is not None and canonical in PROMPT_REGISTRY:
        return canonical
    known = ", ".join(sorted(PROMPT_REGISTRY))
    raise KeyError(f"Unknown prompt {name!r}; known prompts: {known}")


def _semver_key(version: str) -> tuple[int, ...]:
    """Best-effort numeric sort key for a ``"major.minor.patch"`` version string."""
    parts: list[int] = []
    for chunk in str(version).replace("-", ".").split("."):
        digits = "".join(char for char in chunk if char.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


def list_prompts() -> list[str]:
    """Canonical names of every registered prompt, sorted."""
    return sorted(PROMPT_REGISTRY)


def get_prompt(name: str, version: str | None = None) -> PromptRecord:
    """Return the :class:`PromptRecord` for ``name`` (newest version by default).

    ``name`` accepts the module name, its graph-node name, or a documented
    synonym (see :data:`ALIASES`).

    Raises:
        KeyError: when the prompt name is unknown, or when ``version`` is not a
            registered version of that prompt.
    """
    canonical = _resolve(name)
    versions = PROMPT_REGISTRY[canonical]
    if version is None:
        return versions[max(versions, key=_semver_key)]
    if version not in versions:
        known = ", ".join(sorted(versions, key=_semver_key))
        raise KeyError(
            f"Prompt {canonical!r} has no version {version!r}; known versions: {known}"
        )
    return versions[version]


def latest_version(name: str) -> str:
    """Highest registered version of ``name``.

    Raises:
        KeyError: when the prompt name is unknown.
    """
    canonical = _resolve(name)
    versions = PROMPT_REGISTRY[canonical]
    return max(versions, key=_semver_key)


def render(
    node: str, *, version: str | None = None, **fields: Any
) -> RenderedPrompt:
    """Render a node's system + user messages, filling in ``fields``.

    Missing fields become ``[not provided: name]``; this function never raises
    ``KeyError``.

    Raises:
        KeyError: when ``node`` or ``version`` is unknown.
    """
    return get_prompt(node, version).render(**fields)
