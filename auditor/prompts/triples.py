"""Prompt for the triples node (PRD §8.5, §23) — Agent 4, semantic triples.

Builds subject–predicate–object triples for the knowledge graph. Only relationships
the page states (or clearly implies) may be emitted; unsupported ones are marked
``unsupported``/``missing`` instead of being invented.
"""

from __future__ import annotations

from auditor.prompts._shared import GUARDRAILS, PromptExample

#: Registry key for this prompt.
NAME = "triples"
#: Graph node this prompt is wired to in ``auditor.workflows.audit_graph``.
WORKFLOW_NODE = "triples_agent"
#: Semantic version — bump on any wording or schema change.
PROMPT_VERSION = "1.0.0"
#: One-line description for the UI / prompt inspector.
SUMMARY = "Extract subject–predicate–object triples that represent the page's facts."

SYSTEM = (
    "You are Agent 4 — the Semantic Triple / KG Agent for EntityGraph Auditor.\n"
    "Turn the page into subject–predicate–object triples for a knowledge graph. A\n"
    "triple must be traceable to the page: emit 'explicit' only for stated relations,\n"
    "'implied' for strongly suggested ones, and 'missing' for relations the page ought\n"
    "to state but does not. Never import relations from outside the supplied text.\n"
    "\n"
    "Your reply MUST be a single JSON object matching this JSON Schema:\n"
    "{schema_json}\n"
    "\n"
    + GUARDRAILS
)

USER_TEMPLATE = """Extract the semantic triples asserted by this page.

<untrusted_content>
{content}
</untrusted_content>

Known entities (for subject/object wording; do not add new ones from elsewhere):
{entities_json}

Context:
- page_url: {page_url}
- central_entity: {central_entity}

Return only JSON matching the provided schema.
"""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["triples"],
    "properties": {
        "triples": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["triple_id", "subject", "predicate", "object_"],
                "properties": {
                    "triple_id": {"type": "string"},
                    "subject": {"type": "string"},
                    "predicate": {"type": "string"},
                    "object_": {"type": "string"},
                    "triple_type": {
                        "type": "string",
                        "enum": [
                            "category",
                            "capability",
                            "audience",
                            "geography",
                            "process",
                            "outcome",
                            "price",
                            "integration",
                            "authority",
                            "comparison",
                            "requirement",
                            "safety_compliance",
                            "cause_effect",
                            "other",
                        ],
                    },
                    "status": {
                        "type": "string",
                        "enum": ["explicit", "implied", "missing", "wrong", "unsupported"],
                    },
                    "evidence_excerpt": {"type": ["string", "null"]},
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "not_assessed"],
                    },
                },
            },
        }
    },
}

EXAMPLES: list[PromptExample] = [
    PromptExample(
        id="triples-correct",
        valid=True,
        user_fields={
            "content": "<p>Acme Roof Inspection serves Denver, CO. Inspections cost from $149.</p>",
            "entities_json": '[{"entity_id": "ent-1", "canonical_name": "Acme Roof Inspection"}]',
            "page_url": "https://example.com/roof-inspection",
            "central_entity": "Acme Roof Inspection",
        },
        output=(
            '{"triples": ['
            '{"triple_id": "tr-1", "subject": "Acme Roof Inspection", '
            '"predicate": "serves", "object_": "Denver, CO", '
            '"triple_type": "geography", "status": "explicit", '
            '"evidence_excerpt": "Acme Roof Inspection serves Denver, CO.", '
            '"confidence": "high"}, '
            '{"triple_id": "tr-2", "subject": "Acme Roof Inspection", '
            '"predicate": "charges starting price", "object_": "$149", '
            '"triple_type": "price", "status": "explicit", "evidence_excerpt": null, '
            '"confidence": "medium"}]}'
        ),
        why="Every triple points at text on the page and carries a status.",
    ),
    PromptExample(
        id="triples-incorrect",
        valid=False,
        user_fields={"content": "Page text.", "entities_json": "[]"},
        output=(
            '{"triples": [{"triple_id": "tr-1", "subject": "Acme Roof Inspection", '
            '"predicate": "is certified by", "triple_type": "authority", '
            '"status": "explicit", "confidence": "high"}]}'
        ),
        why=(
            "The required key 'object_' is missing, and the certification relationship it "
            "would have asserted is unsupported by the supplied text."
        ),
    ),
]
