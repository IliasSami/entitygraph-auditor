"""Backwards-compatibility shim over :mod:`auditor.prompts` (PRD §23).

Earlier revisions of this project stored one flat prompt string per agent in this
module. Those names are still imported by ``auditor.agents.*``, so they are
preserved here — but each one now resolves to the *versioned* prompt that lives in
its own node module (``auditor.prompts.classifier``, ````.fanout``, …).

The constants below are the fully-rendered **system** prompts: the node's schema is
already substituted into the text, so they are safe to pass straight to
``ModelCallRequest(system_prompt=...)`` exactly as before.

New code should prefer the registry API::

    from auditor.prompts import get_prompt, render
    record = get_prompt("claims")           # or "claims_agent"
    messages = render("claims", content=text, entities_json=json.dumps(ents))

There is one source of truth: :data:`auditor.prompts.PROMPT_REGISTRY`.
"""

from __future__ import annotations

from typing import Any

from auditor.prompts import (
    ALIASES,
    DEFAULT_PROMPT_VERSION,
    PROMPT_REGISTRY,
    get_prompt,
    latest_version,
    list_prompts,
    render,
)

__all__ = [
    "ALIASES",
    "CLAIMS_AGENT_PROMPT",
    "COVERAGE_AGENT_PROMPT",
    "CRITIC_AGENT_PROMPT",
    "EDITORIAL_AGENT_PROMPT",
    "ENTITY_EAV_PROMPT",
    "FANOUT_AGENT_PROMPT",
    "GATE_AGENT_PROMPT",
    "HANDOFF_AGENT_PROMPT",
    "INTAKE_CLASSIFIER_PROMPT",
    "PASSAGES_AGENT_PROMPT",
    "PROMPT_REGISTRY",
    "PROMPT_VERSION",
    "SYSTEM_PROMPTS",
    "TRIPLES_AGENT_PROMPT",
    "build_user_prompt",
    "get_prompt",
    "latest_version",
    "list_prompts",
    "render",
]

#: Version of the legacy constant set; tracks the node prompts it re-exports.
PROMPT_VERSION: str = DEFAULT_PROMPT_VERSION


def _system(node: str) -> str:
    """Fully-rendered system prompt for ``node`` (schema already substituted)."""
    return render(node).system


def _user(node: str, **fields: Any) -> str:
    """Fully-rendered user prompt for ``node`` (missing fields are placeholdered)."""
    return render(node, **fields).user


# -- legacy agent-facing system prompts (graph node aliases in brackets) ---------- #

#: Agent 1 — intake & page-type classifier (node ``intake_classifier``).
INTAKE_CLASSIFIER_PROMPT: str = _system("classifier")

#: Agent 2 — query / fan-out research (node ``fanout_agent``).
FANOUT_AGENT_PROMPT: str = _system("fanout")

#: Agent 3 — entity & EAV extraction (node ``entity_eav_agent``).
ENTITY_EAV_PROMPT: str = _system("entities")

#: Agent 4 — semantic triple / KG extraction (node ``triples_agent``).
TRIPLES_AGENT_PROMPT: str = _system("triples")

#: Passage labelling (reserved graph stage ``passages``).
PASSAGES_AGENT_PROMPT: str = _system("passages")

#: Agent 6 — evidence / claim verification (node ``claims_agent``).
CLAIMS_AGENT_PROMPT: str = _system("claims")

#: Agent 8 — coverage & gap analysis (node ``coverage_agent``).
COVERAGE_AGENT_PROMPT: str = _system("coverage")

#: Agent 9 — human utility / editorial review (node ``editorial_agent``).
EDITORIAL_AGENT_PROMPT: str = _system("editorial")

#: Quality gate (shared QA stage ``gate``).
GATE_AGENT_PROMPT: str = _system("gate")

#: Agent 12 — priority & writer hand-off (node ``handoff_agent``).
HANDOFF_AGENT_PROMPT: str = _system("handoff")

#: Agent 13 — critic / QA (node ``critic_agent``).
CRITIC_AGENT_PROMPT: str = _system("critic")

#: Legacy constant name -> rendered system prompt, for callers that iterate.
SYSTEM_PROMPTS: dict[str, str] = {
    "INTAKE_CLASSIFIER_PROMPT": INTAKE_CLASSIFIER_PROMPT,
    "FANOUT_AGENT_PROMPT": FANOUT_AGENT_PROMPT,
    "ENTITY_EAV_PROMPT": ENTITY_EAV_PROMPT,
    "TRIPLES_AGENT_PROMPT": TRIPLES_AGENT_PROMPT,
    "PASSAGES_AGENT_PROMPT": PASSAGES_AGENT_PROMPT,
    "CLAIMS_AGENT_PROMPT": CLAIMS_AGENT_PROMPT,
    "COVERAGE_AGENT_PROMPT": COVERAGE_AGENT_PROMPT,
    "EDITORIAL_AGENT_PROMPT": EDITORIAL_AGENT_PROMPT,
    "GATE_AGENT_PROMPT": GATE_AGENT_PROMPT,
    "HANDOFF_AGENT_PROMPT": HANDOFF_AGENT_PROMPT,
    "CRITIC_AGENT_PROMPT": CRITIC_AGENT_PROMPT,
}


def build_user_prompt(node: str, *, version: str | None = None, **fields: Any) -> str:
    """Rendered user message for ``node`` — replaces the old per-agent f-strings."""
    return render(node, version=version, **fields).user
