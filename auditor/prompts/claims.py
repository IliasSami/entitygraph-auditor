"""Prompt for the claims node (PRD §8.7, §23) — Agent 6, claim verification.

Surfaces empirical, statistical, medical, financial and competitive claims and marks
whether the supplied material substantiates them. Unverified stays ``unverified``;
it is never upgraded to ``verified`` on the strength of the page's own assertion.
"""

from __future__ import annotations

from auditor.prompts._shared import GUARDRAILS, PromptExample

#: Registry key for this prompt.
NAME = "claims"
#: Graph node this prompt is wired to in ``auditor.workflows.audit_graph``.
WORKFLOW_NODE = "claims_agent"
#: Semantic version — bump on any wording or schema change.
PROMPT_VERSION = "1.0.0"
#: One-line description for the UI / prompt inspector.
SUMMARY = "Flag empirical claims and record whether the supplied material substantiates them."

SYSTEM = (
    "You are Agent 6 — the Evidence / Claim Verification Agent for EntityGraph Auditor.\n"
    "You isolate the claims a page makes — statistical, medical, financial, competitive,\n"
    "otherwise empirical — and record what the supplied material does and does not\n"
    "substantiate. A page asserting something about itself is not evidence for it.\n"
    "Verification state is 'not_assessed' unless you were actually given a source.\n"
    "\n"
    "Your reply MUST be a single JSON object matching this JSON Schema:\n"
    "{schema_json}\n"
    "\n"
    + GUARDRAILS
)

USER_TEMPLATE = """Identify and assess the claims made on this page.

<untrusted_content>
{content}
</untrusted_content>

Known entities (context only; do not treat them as evidence):
{entities_json}

Context:
- page_url: {page_url}
- central_entity: {central_entity}

Return only JSON matching the provided schema.
"""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["claims"],
    "properties": {
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["claim_id", "statement", "risk_tier", "verification_state"],
                "properties": {
                    "claim_id": {"type": "string"},
                    "statement": {"type": "string"},
                    "risk_tier": {
                        "type": "string",
                        "enum": ["ordinary", "high_stakes", "regulated"],
                    },
                    "verification_state": {
                        "type": "string",
                        "enum": ["verified", "unverified", "conflicting", "not_assessed"],
                    },
                    "requires_substantiation": {"type": "boolean"},
                    "evidence_source_ids": {"type": "array", "items": {"type": "string"}},
                    "issue": {"type": ["string", "null"]},
                    "evidence_excerpt": {"type": ["string", "null"]},
                },
            },
        }
    },
}

EXAMPLES: list[PromptExample] = [
    PromptExample(
        id="claims-correct",
        valid=True,
        user_fields={
            "content": "<p>Our inspections catch 98% of leaks. Denver homeowners trust us.</p>",
            "entities_json": '[{"entity_id": "ent-1", "canonical_name": "Acme"}]',
            "page_url": "https://example.com/roof-inspection",
            "central_entity": "Acme Roof Inspection",
        },
        output=(
            '{"claims": ['
            '{"claim_id": "cl-1", "statement": "Our inspections catch 98% of leaks.", '
            '"risk_tier": "high_stakes", "verification_state": "unverified", '
            '"requires_substantiation": true, "evidence_source_ids": [], '
            '"issue": "No study, dataset or methodology is cited for the 98% figure.", '
            '"evidence_excerpt": "Our inspections catch 98% of leaks."}]}'
        ),
        why="The statistic is reported as unverified rather than accepted at face value.",
    ),
    PromptExample(
        id="claims-incorrect",
        valid=False,
        user_fields={"content": "Page text.", "entities_json": "[]"},
        output='{"claims": [{"claim_id": "cl-1", "risk_tier": "ordinary"}]}',
        why=(
            "The claim's 'statement' and 'verification_state' are both missing — an "
            "unnamed claim cannot be checked, and the schema refuses to keep it."
        ),
    ),
]
