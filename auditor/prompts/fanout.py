"""Prompt for the fanout node (PRD §8.3, §23) — Agent 2, query fan-out.

Generates the 4–8 sub-queries an answer engine would ask about this page. Every
query must be *derived from the supplied material* — no invented statistics, no
invented sources.
"""

from __future__ import annotations

from auditor.prompts._shared import GUARDRAILS, PromptExample

#: Registry key for this prompt.
NAME = "fanout"
#: Graph node this prompt is wired to in ``auditor.workflows.audit_graph``.
WORKFLOW_NODE = "fanout_agent"
#: Semantic version — bump on any wording or schema change.
PROMPT_VERSION = "1.0.0"
#: One-line description for the UI / prompt inspector.
SUMMARY = "Generate the essential sub-queries (fan-out) a searcher or AI engine would ask."

SYSTEM = (
    "You are Agent 2 — the Query / Fan-out Research Agent for EntityGraph Auditor.\n"
    "Given one page, you produce the small set of follow-up questions that a searcher\n"
    "or an AI answer engine would ask about the same topic, and you classify each one.\n"
    "Write queries from the page's own subject matter; do not pad the list and do not\n"
    "claim a source you have not been shown.\n"
    "\n"
    "Your reply MUST be a single JSON object matching this JSON Schema:\n"
    "{schema_json}\n"
    "\n"
    + GUARDRAILS
)

USER_TEMPLATE = """Generate the fan-out queries for this page.

<untrusted_content>
{content}
</untrusted_content>

Context:
- page_url: {page_url}
- page_type: {page_type}
- central_entity: {central_entity}
- primary_intent: {primary_intent}

Return only JSON matching the provided schema.
"""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["fanout_queries"],
    "properties": {
        "fanout_queries": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["query_id", "query_text"],
                "properties": {
                    "query_id": {"type": "string"},
                    "query_text": {"type": "string"},
                    "origin": {"type": "string", "enum": ["observed", "simulated"]},
                    "source": {
                        "type": "string",
                        "enum": [
                            "gsc",
                            "bing",
                            "serp_paa",
                            "user_brief",
                            "competitor",
                            "topical_map",
                            "generated_hypothesis",
                            "other",
                        ],
                    },
                    "intent": {
                        "type": "string",
                        "enum": [
                            "informational",
                            "commercial",
                            "transactional",
                            "navigational",
                            "local",
                            "comparison",
                            "evaluation",
                            "research",
                        ],
                    },
                    "importance": {"type": "integer", "enum": [1, 2, 3]},
                    "answer_shape": {
                        "type": "string",
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
                    "scope": {
                        "type": "string",
                        "enum": ["this_page", "sibling_page", "out_of_scope"],
                    },
                },
            },
        }
    },
}

EXAMPLES: list[PromptExample] = [
    PromptExample(
        id="fanout-correct",
        valid=True,
        user_fields={
            "content": "<h1>Roof Inspection in Denver</h1><p>Free inspections after hail storms.</p>",
            "page_url": "https://example.com/roof-inspection",
            "page_type": "service",
            "central_entity": "Acme Roof Inspection",
            "primary_intent": "commercial",
        },
        output=(
            '{"fanout_queries": ['
            '{"query_id": "fo-1", "query_text": "How much does a roof inspection cost in Denver?", '
            '"origin": "simulated", "source": "generated_hypothesis", "intent": "commercial", '
            '"importance": 3, "answer_shape": "pricing_fact", "scope": "this_page"}, '
            '{"query_id": "fo-2", "query_text": "How long does a hail-damaged roof last unrepaired?", '
            '"origin": "simulated", "source": "generated_hypothesis", "intent": "informational", '
            '"importance": 1, "answer_shape": "definition", "scope": "this_page"}]}'
        ),
        why="All required keys present; enum values match the shared enum sets.",
    ),
    PromptExample(
        id="fanout-incorrect",
        valid=False,
        user_fields={"content": "Page text.", "page_url": "https://example.com/x"},
        output=(
            '{"queries": [{"query_id": "fo-1", "query_text": "Is this the best roofer in Denver?"}]}'
        ),
        why=(
            "The required top-level key 'fanout_queries' is missing (the model renamed it "
            "'queries'), so downstream coverage has nothing to read."
        ),
    ),
]
