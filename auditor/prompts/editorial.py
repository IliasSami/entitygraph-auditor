"""Prompt for the editorial node (PRD §8.9, §23) — Agent 9, human utility.

Judges tone, clarity and scannability for a human reader. Findings must quote what is
wrong on the page — a generic writing tip that could apply anywhere is not a finding.
"""

from __future__ import annotations

from auditor.prompts._shared import GUARDRAILS, PromptExample

#: Registry key for this prompt.
NAME = "editorial"
#: Graph node this prompt is wired to in ``auditor.workflows.audit_graph``.
WORKFLOW_NODE = "editorial_agent"
#: Semantic version — bump on any wording or schema change.
PROMPT_VERSION = "1.0.0"
#: One-line description for the UI / prompt inspector.
SUMMARY = "Judge readability, tone and scannability, with findings grounded in the page."

SYSTEM = (
    "You are Agent 9 — the Human Utility / Editorial Agent for EntityGraph Auditor.\n"
    "You read as a demanding human reader: is the page clear, skimmable, honest about\n"
    "what it offers, and worth the time? Every finding you raise must point at something\n"
    "specific on THIS page. Advice that would fit any page is noise — do not emit it.\n"
    "\n"
    "Your reply MUST be a single JSON object matching this JSON Schema:\n"
    "{schema_json}\n"
    "\n"
    + GUARDRAILS
)

USER_TEMPLATE = """Assess the readability and human utility of this page.

<untrusted_content>
{content}
</untrusted_content>

Already-detected coverage gaps (do not repeat them as editorial findings):
{coverage_json}

Context:
- page_url: {page_url}
- page_type: {page_type}
- central_entity: {central_entity}

Return only JSON matching the provided schema.
"""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["editorial_findings"],
    "properties": {
        "editorial_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["finding_id", "category", "severity", "title", "what"],
                "properties": {
                    "finding_id": {"type": "string"},
                    "category": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "high", "medium", "low", "info"],
                    },
                    "title": {"type": "string"},
                    "what": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "not_assessed"],
                    },
                    "impact": {"type": "integer"},
                    "confidence_numeric": {"type": "integer"},
                    "effort": {"type": "integer"},
                    "priority_score": {"type": "number"},
                    "status": {
                        "type": "string",
                        "enum": ["open", "in_progress", "done", "dismissed"],
                    },
                },
            },
        }
    },
}

EXAMPLES: list[PromptExample] = [
    PromptExample(
        id="editorial-correct",
        valid=True,
        user_fields={
            "content": "<h1>Roof Inspection</h1><p>We do roofs.</p><p>Contact us.</p>",
            "coverage_json": "[]",
            "page_url": "https://example.com/roof-inspection",
            "page_type": "service",
            "central_entity": "Acme Roof Inspection",
        },
        output=(
            '{"editorial_findings": ['
            '{"finding_id": "F-ED-1", "category": "readability_utility", '
            '"severity": "medium", '
            '"title": "Body copy never says what an inspection includes", '
            '"what": "The two body sentences state no deliverable, price or timeframe, '
            'so a reader cannot tell what is being sold.", '
            '"evidence": ["We do roofs."], "confidence": "high", "impact": 4, '
            '"confidence_numeric": 5, "effort": 1, "priority_score": 20.0, '
            '"status": "open"}]}'
        ),
        why="The finding quotes the page it is about instead of offering generic advice.",
    ),
    PromptExample(
        id="editorial-incorrect",
        valid=False,
        user_fields={"content": "Page text.", "coverage_json": "[]"},
        output=(
            '{"editorial_findings": [{"finding_id": "F-ED-1", '
            '"category": "readability_utility", "severity": "low", "what": "Improve tone"}]}'
        ),
        why=(
            "The finding has no 'title', so it cannot be rendered in a report — and "
            "'Improve tone' with no quoted evidence is generic advice, which this node "
            "is explicitly told not to emit."
        ),
    ),
]
