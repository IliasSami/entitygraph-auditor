"""Prompt for the classifier node (PRD §8.2, §23) — Agent 1, intake & page type.

The model only *reads*: it labels the page type, names the central entity and
states the search intent. Anything the text does not support must come back
``null``/``not_assessed`` rather than being guessed (PRD §13.3, FR-22).
"""

from __future__ import annotations

from auditor.prompts._shared import GUARDRAILS, PromptExample

#: Registry key for this prompt.
NAME = "classifier"
#: Graph node this prompt is wired to in ``auditor.workflows.audit_graph``.
WORKFLOW_NODE = "intake_classifier"
#: Semantic version — bump on any wording or schema change.
PROMPT_VERSION = "1.0.0"
#: One-line description for the UI / prompt inspector.
SUMMARY = "Classify page type, central entity, search intent, audience and target action."

SYSTEM = (
    "You are Agent 1 — the Intake & Page-Type Classifier for EntityGraph Auditor.\n"
    "You receive the text of exactly one web page and return its classification: page\n"
    "type, central entity, primary search intent, target audience and target action.\n"
    "You are a classifier, not an author: state only what the page supports and leave\n"
    "the rest null.\n"
    "\n"
    "Your reply MUST be a single JSON object matching this JSON Schema:\n"
    "{schema_json}\n"
    "\n"
    + GUARDRAILS
)

USER_TEMPLATE = """Classify the page below.

<untrusted_content>
{content}
</untrusted_content>

Caller hints (an explicit user hint always beats your own reading):
- page_url: {page_url}
- known page_type: {page_type}
- known central_entity: {central_entity}
- locale: {locale}

Return only JSON matching the provided schema.
"""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["page_type", "central_entity", "primary_intent"],
    "properties": {
        "page_type": {
            "type": "string",
            "enum": [
                "homepage",
                "about",
                "service",
                "local_service",
                "article",
                "glossary",
                "listicle",
                "comparison",
                "case_study",
                "saas_b2b",
                "integration",
                "paid_landing",
                "product_category",
                "trust_policy",
                "docs",
                "general",
            ],
        },
        "central_entity": {"type": ["string", "null"]},
        "primary_intent": {
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
        "target_audience": {"type": ["string", "null"]},
        "target_action": {"type": ["string", "null"]},
        "locale": {"type": ["string", "null"]},
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low", "not_assessed"],
        },
        "assumptions": {"type": "array", "items": {"type": "string"}},
    },
}

EXAMPLES: list[PromptExample] = [
    PromptExample(
        id="classifier-correct",
        valid=True,
        user_fields={
            "content": "<h1>Roof Inspection in Denver</h1>\n<p>We inspect and repair storm-damaged roofs. Book a free inspection.</p>",
            "page_url": "https://example.com/roof-inspection",
            "page_type": "service",
            "central_entity": None,
            "locale": "en",
        },
        output=(
            '{"page_type": "service", "central_entity": "Acme Roof Inspection", '
            '"primary_intent": "commercial", '
            '"target_audience": "Denver homeowners with storm-damaged roofs", '
            '"target_action": "Request a free roof inspection", "locale": "en", '
            '"confidence": "high", "assumptions": ["The page offers a paid service."]}'
        ),
        why="Every required key is present, every enum value is in the schema.",
    ),
    PromptExample(
        id="classifier-incorrect",
        valid=False,
        user_fields={
            "content": "Any page text at all.",
            "page_url": "https://example.com/unknown",
        },
        output=(
            'The page looks like a service page to me. Here is the JSON:\n'
            '{"page_type": "service", "primary_intent": "commercial", "confidence": "high"}'
        ),
        why=(
            "Prose surrounds the JSON and the required key 'central_entity' is missing, "
            "so the model invented a classification the schema never allowed."
        ),
    ),
]
