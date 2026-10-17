"""Prompt for the critic node (PRD §8.12, §23) — Agent 13, QA / critic.

Checks the assembled run for contradictions, arithmetic errors and fabricated
citations, then approves or rejects. The critic's job is to *withhold* approval when
the run is wrong; approval must be justified, never assumed.
"""

from __future__ import annotations

from auditor.prompts._shared import GUARDRAILS, PromptExample

#: Registry key for this prompt.
NAME = "critic"
#: Graph node this prompt is wired to in ``auditor.workflows.audit_graph``.
WORKFLOW_NODE = "critic_agent"
#: Semantic version — bump on any wording or schema change.
PROMPT_VERSION = "1.0.0"
#: One-line description for the UI / prompt inspector.
SUMMARY = "QA the assembled run for contradictions, arithmetic errors and fabricated sources."

SYSTEM = (
    "You are Agent 13 — the Critic / QA Agent for EntityGraph Auditor.\n"
    "You audit the audit. Check the run for internal contradictions, arithmetic that\n"
    "does not add up, findings that contradict their own evidence, and any source,\n"
    "quote or statistic that the run cannot point to. Approve only when the run survives\n"
    "all of those; otherwise list exactly what failed.\n"
    "\n"
    "Your reply MUST be a single JSON object matching this JSON Schema:\n"
    "{schema_json}\n"
    "\n"
    + GUARDRAILS
)

USER_TEMPLATE = """Critique this audit run.

<untrusted_content>
{run_summary}
</untrusted_content>

Items the run must satisfy:
{checklist}

Context:
- page_url: {page_url}
- central_entity: {central_entity}

Return only JSON matching the provided schema.
"""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["critic_approved", "issues"],
    "properties": {
        "critic_approved": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": ["string", "null"]},
        "checked_items": {"type": "array", "items": {"type": "string"}},
    },
}

EXAMPLES: list[PromptExample] = [
    PromptExample(
        id="critic-correct",
        valid=True,
        user_fields={
            "run_summary": '{"findings": [{"finding_id": "F-1"}], "scores": {"entity_clarity": 8}}',
            "checklist": "- [ ] every finding has evidence\n- [ ] scores within 0-10",
            "page_url": "https://example.com/roof-inspection",
            "central_entity": "Acme Roof Inspection",
        },
        output=(
            '{"critic_approved": false, '
            '"issues": ["F-1 cites a warranty claim that appears nowhere in the extracted claims."], '
            '"notes": "One unsupported finding; scores otherwise in range.", '
            '"checked_items": ["finding evidence", "score range"]}'
        ),
        why="The critic found a real contradiction and withheld approval.",
    ),
    PromptExample(
        id="critic-incorrect",
        valid=False,
        user_fields={"run_summary": "{}", "checklist": "- [ ] everything"},
        output='{"critic_approved": "yes", "issues": []}',
        why=(
            "'critic_approved' must be a JSON boolean; the string \"yes\" cannot be "
            "interpreted as approval by the gate, so the schema rejects the reply."
        ),
    ),
]
