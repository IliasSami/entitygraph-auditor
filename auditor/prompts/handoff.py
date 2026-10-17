"""Prompt for the handoff node (PRD §8.11, §23) — Agent 12, writer hand-off.

Turns findings into prioritised, actionable recommendations. Priority follows the PRD
§9.6 formula ``(impact x confidence) / effort``; the model supplies the inputs and a
concrete rewrite, never a fabricated benchmark.
"""

from __future__ import annotations

from auditor.prompts._shared import GUARDRAILS, PromptExample

#: Registry key for this prompt.
NAME = "handoff"
#: Graph node this prompt is wired to in ``auditor.workflows.audit_graph``.
WORKFLOW_NODE = "handoff_agent"
#: Semantic version — bump on any wording or schema change.
PROMPT_VERSION = "1.0.0"
#: One-line description for the UI / prompt inspector.
SUMMARY = "Turn findings into prioritised recommendations with rewrites and a measurement plan."

SYSTEM = (
    "You are Agent 12 — the Priority & Writer-Handoff Agent for EntityGraph Auditor.\n"
    "You convert the audit's findings into work a writer can start immediately: one\n"
    "clear action each, with a concrete suggested rewrite, the condition a human must\n"
    "verify before shipping it, and the steps to get there. Impact, confidence and\n"
    "effort are integers from 1 to 5 and drive the priority score; do not quote\n"
    "benchmarks, traffic figures or studies you were not given.\n"
    "\n"
    "Your reply MUST be a single JSON object matching this JSON Schema:\n"
    "{schema_json}\n"
    "\n"
    + GUARDRAILS
)

USER_TEMPLATE = """Produce the prioritised writer hand-off for this run.

<untrusted_content>
{findings}
</untrusted_content>

Coverage rows:
{coverage_json}

Context:
- page_url: {page_url}
- page_type: {page_type}
- central_entity: {central_entity}

Return only JSON matching the provided schema.
"""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["recommendations", "measurement_plan"],
    "properties": {
        "recommendations": {
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
                    "how": {
                        "type": "object",
                        "required": ["implementation_steps"],
                        "properties": {
                            "suggested_rewrite": {"type": ["string", "null"]},
                            "verification_condition": {"type": ["string", "null"]},
                            "implementation_steps": {"type": "array", "items": {"type": "string"}},
                        },
                    },
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
        },
        "measurement_plan": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["metric", "method"],
                "properties": {
                    "metric": {"type": "string"},
                    "method": {"type": "string"},
                    "baseline": {"type": ["string", "null"]},
                    "target": {"type": ["string", "null"]},
                },
            },
        },
    },
}

EXAMPLES: list[PromptExample] = [
    PromptExample(
        id="handoff-correct",
        valid=True,
        user_fields={
            "findings": '[{"finding_id": "F-CV-1", "title": "No pricing anywhere on the page"}]',
            "coverage_json": '[{"query_id": "fo-1", "status": "missing"}]',
            "page_url": "https://example.com/roof-inspection",
            "page_type": "service",
            "central_entity": "Acme Roof Inspection",
        },
        output=(
            '{"recommendations": ['
            '{"finding_id": "F-CV-1", "category": "coverage", "severity": "high", '
            '"title": "State the inspection price on the page", '
            '"what": "The pricing query scores missing: no price appears in the text.", '
            '"how": {"suggested_rewrite": "Roof inspections start at $149.", '
            '"verification_condition": "Confirm $149 against the current price list.", '
            '"implementation_steps": ["Add a price line under the hero heading"]}, '
            '"confidence": "high", "impact": 4, "confidence_numeric": 5, "effort": 1, '
            '"priority_score": 20.0, "status": "open"}], '
            '"measurement_plan": ['
            '{"metric": "Impressions for roofing inspection cost queries", '
            '"method": "Search Console query group, 28-day window", '
            '"baseline": "0", "target": "1000"}]}'
        ),
        why="Complete recommendation plus a measurable plan; no invented benchmarks.",
    ),
    PromptExample(
        id="handoff-incorrect",
        valid=False,
        user_fields={"findings": "[]", "coverage_json": "[]"},
        output=(
            '{"recommendations": ['
            '{"finding_id": "F-CV-1", "category": "coverage", "severity": "high", '
            '"title": "State the price", "what": "No price is on the page.", '
            '"how": {"implementation_steps": "Add a pricing table below the hero."}}], '
            '"measurement_plan": []}'
        ),
        why=(
            "'implementation_steps' must be an array of steps; a single sentence string "
            "cannot be tracked as a checklist, so the schema rejects it."
        ),
    ),
]
