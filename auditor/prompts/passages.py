"""Prompt for the passages node (PRD §8.6, §23) — passage labelling.

The deterministic parser already splits the document into passages; this node only
*labels* them (answer shape, answer-first structure, issues). It must not rewrite
or invent passage text.
"""

from __future__ import annotations

from auditor.prompts._shared import GUARDRAILS, PromptExample

#: Registry key for this prompt.
NAME = "passages"
#: Graph node this prompt is wired to (no dedicated agent yet; reserved by the graph).
WORKFLOW_NODE = None
#: Semantic version — bump on any wording or schema change.
PROMPT_VERSION = "1.0.0"
#: One-line description for the UI / prompt inspector.
SUMMARY = "Label each parser-produced passage with its answer shape and structural issues."

SYSTEM = (
    "You are the Passage Labelling Agent for EntityGraph Auditor.\n"
    "You are handed passages that a deterministic parser already extracted, and you\n"
    "label each one: does it lead with an answer, which answer shape does it use, what\n"
    "is structurally wrong with it. You never rewrite, re-order or invent passages —\n"
    "the text you were given is the text you report on.\n"
    "\n"
    "Your reply MUST be a single JSON object matching this JSON Schema:\n"
    "{schema_json}\n"
    "\n"
    + GUARDRAILS
)

USER_TEMPLATE = """Label the passages below.

<untrusted_content>
{passages}
</untrusted_content>

Context:
- page_url: {page_url}
- page_type: {page_type}
- central_entity: {central_entity}

Return only JSON matching the provided schema.
"""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["passage_rows"],
    "properties": {
        "passage_rows": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["passage_id", "answer_first"],
                "properties": {
                    "passage_id": {"type": "string"},
                    "answer_shape": {
                        "type": ["string", "null"],
                        "enum": [
                            "definition",
                            "checklist",
                            "procedure",
                            "shortlist",
                            "table",
                            "comparison_verdict",
                            "pricing_fact",
                            "risk_explanation",
                            "proof_block",
                            "cta",
                        ],
                    },
                    "answer_first": {"type": "boolean"},
                    "named_subject": {"type": "boolean"},
                    "word_count": {"type": "integer"},
                    "issues": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": ["string", "null"]},
                },
            },
        }
    },
}

EXAMPLES: list[PromptExample] = [
    PromptExample(
        id="passages-correct",
        valid=True,
        user_fields={
            "passages": '[{"passage_id": "p-1", "text": "A roof inspection costs $149 in Denver."}]',
            "page_url": "https://example.com/roof-inspection",
            "page_type": "service",
            "central_entity": "Acme Roof Inspection",
        },
        output=(
            '{"passage_rows": ['
            '{"passage_id": "p-1", "answer_shape": "pricing_fact", "answer_first": true, '
            '"named_subject": false, "word_count": 8, "issues": [], "notes": null}]}'
        ),
        why="Labels only; the passage id and the boolean answer_first are both present.",
    ),
    PromptExample(
        id="passages-incorrect",
        valid=False,
        user_fields={"passages": "[]", "page_url": "https://example.com/x"},
        output='{"passage_rows": "p-1, p-2"}',
        why=(
            "'passage_rows' must be an array of objects; a comma-joined id string is the "
            "wrong type, so no row can be matched back to the parser's output."
        ),
    ),
]
