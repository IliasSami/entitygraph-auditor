"""Prompt for the coverage node (PRD §8.8, §23) — Agent 8, coverage & gaps.

Matches the fan-out queries against the page's own passages and scores coverage from
0–1. A query the page does not answer is ``missing`` — never ``covered`` on a
neighbouring topic.
"""

from __future__ import annotations

from auditor.prompts._shared import GUARDRAILS, PromptExample

#: Registry key for this prompt.
NAME = "coverage"
#: Graph node this prompt is wired to in ``auditor.workflows.audit_graph``.
WORKFLOW_NODE = "coverage_agent"
#: Semantic version — bump on any wording or schema change.
PROMPT_VERSION = "1.0.0"
#: One-line description for the UI / prompt inspector.
SUMMARY = "Score how well the page answers each fan-out query and name the gaps."

SYSTEM = (
    "You are Agent 8 — the Coverage & Gap Agent for EntityGraph Auditor.\n"
    "You are given the page's passages and a list of fan-out queries. For each query\n"
    "you decide whether THIS page answers it — covered, partially, not at all, or out of\n"
    "scope — and say precisely why. Adjacent-but-different answers count as partial or\n"
    "missing; you do not credit a page for answering a question it never addresses.\n"
    "\n"
    "Your reply MUST be a single JSON object matching this JSON Schema:\n"
    "{schema_json}\n"
    "\n"
    + GUARDRAILS
)

USER_TEMPLATE = """Score the page's coverage of each fan-out query.

<untrusted_content>
{content}
</untrusted_content>

Queries to score:
{fanout_json}

Context:
- page_url: {page_url}
- central_entity: {central_entity}

Return only JSON matching the provided schema.
"""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["coverage_rows"],
    "properties": {
        "coverage_rows": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["query_id", "query_text", "status"],
                "properties": {
                    "query_id": {"type": "string"},
                    "query_text": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["covered", "partial", "missing", "excluded"],
                    },
                    "matched_passage_ids": {"type": "array", "items": {"type": "string"}},
                    "coverage_score": {"type": "number"},
                    "gap_reason": {"type": ["string", "null"]},
                    "destination_page": {"type": ["string", "null"]},
                },
            },
        }
    },
}

EXAMPLES: list[PromptExample] = [
    PromptExample(
        id="coverage-correct",
        valid=True,
        user_fields={
            "content": '<p class="passage">Roof inspections in Denver start at $149.</p>',
            "fanout_json": '[{"query_id": "fo-1", "query_text": "How much does a roof inspection cost in Denver?"}]',
            "page_url": "https://example.com/roof-inspection",
            "central_entity": "Acme Roof Inspection",
        },
        output=(
            '{"coverage_rows": ['
            '{"query_id": "fo-1", '
            '"query_text": "How much does a roof inspection cost in Denver?", '
            '"status": "covered", "matched_passage_ids": ["p-1"], "coverage_score": 1.0, '
            '"gap_reason": null, "destination_page": null}]}'
        ),
        why="Status, score and the passage it was matched to all agree.",
    ),
    PromptExample(
        id="coverage-incorrect",
        valid=False,
        user_fields={"content": "Passages.", "fanout_json": "[]"},
        output=(
            '{"coverage": [{"query_id": "fo-1", "query_text": "Anything?", '
            '"status": "covered"}]}'
        ),
        why=(
            "The model returned the rows under 'coverage' instead of the required "
            "'coverage_rows', so the coverage score has nothing to read."
        ),
    ),
]
