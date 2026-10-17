"""Prompt for the entities node (PRD §8.4, §23) — Agent 3, entities & EAV.

Extracts the central entity plus supporting entities and the Entity-Attribute-Value
facts the page states about them. A missing attribute is reported as ``missing`` —
never filled in from general knowledge.
"""

from __future__ import annotations

from auditor.prompts._shared import GUARDRAILS, PromptExample

#: Registry key for this prompt.
NAME = "entities"
#: Graph node this prompt is wired to in ``auditor.workflows.audit_graph``.
WORKFLOW_NODE = "entity_eav_agent"
#: Semantic version — bump on any wording or schema change.
PROMPT_VERSION = "1.0.0"
#: One-line description for the UI / prompt inspector.
SUMMARY = "Extract entities and the Entity-Attribute-Value facts the page states about them."

SYSTEM = (
    "You are Agent 3 — the Entity & EAV Agent for EntityGraph Auditor.\n"
    "From one page you extract (a) the entities it names and (b) the\n"
    "Entity-Attribute-Value rows: which attribute of which entity the page actually\n"
    "states, and how clearly. An attribute the page never states is 'missing' — you\n"
    "never supply it from memory or from the open web.\n"
    "\n"
    "Your reply MUST be a single JSON object matching this JSON Schema:\n"
    "{schema_json}\n"
    "\n"
    + GUARDRAILS
)

USER_TEMPLATE = """Extract the entities and EAV facts asserted by this page.

<untrusted_content>
{content}
</untrusted_content>

Context:
- page_url: {page_url}
- page_type: {page_type}
- central_entity: {central_entity}

Return only JSON matching the provided schema.
"""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["entities", "eav_rows"],
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["entity_id", "canonical_name"],
                "properties": {
                    "entity_id": {"type": "string"},
                    "canonical_name": {"type": "string"},
                    "kind": {
                        "type": "string",
                        "enum": [
                            "central",
                            "brand",
                            "organization",
                            "product_service",
                            "person",
                            "location",
                            "concept",
                            "problem",
                            "outcome",
                            "process",
                            "tool",
                            "material",
                            "audience",
                            "use_case",
                            "platform",
                            "competitor",
                            "metric",
                            "price",
                            "date",
                            "standard",
                            "regulation",
                            "proof",
                            "cta",
                            "other",
                        ],
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "not_assessed"],
                    },
                    "salience": {"type": "number"},
                    "is_central": {"type": "boolean"},
                    "aliases": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "eav_rows": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["eav_id", "entity_name", "attribute", "status"],
                "properties": {
                    "eav_id": {"type": "string"},
                    "entity_name": {"type": "string"},
                    "attribute": {"type": "string"},
                    "value": {"type": ["string", "null"]},
                    "status": {
                        "type": "string",
                        "enum": [
                            "explicit",
                            "vague",
                            "missing",
                            "conflicting",
                            "unverified",
                            "not_applicable",
                        ],
                    },
                    "evidence_excerpt": {"type": ["string", "null"]},
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low", "not_assessed"],
                    },
                    "is_required_by_page_type": {"type": "boolean"},
                },
            },
        },
    },
}

EXAMPLES: list[PromptExample] = [
    PromptExample(
        id="entities-correct",
        valid=True,
        user_fields={
            "content": "<h1>Acme Roof Inspection</h1><p>Same-day inspections across Denver, CO. From $149.</p>",
            "page_url": "https://example.com/roof-inspection",
            "page_type": "service",
            "central_entity": "Acme Roof Inspection",
        },
        output=(
            '{"entities": ['
            '{"entity_id": "ent-1", "canonical_name": "Acme Roof Inspection", '
            '"kind": "central", "confidence": "high", "salience": 0.9, '
            '"is_central": true, "aliases": ["Acme"]}, '
            '{"entity_id": "ent-2", "canonical_name": "Denver", "kind": "location", '
            '"confidence": "high", "salience": 0.5, "is_central": false, "aliases": []}], '
            '"eav_rows": ['
            '{"eav_id": "eav-1", "entity_name": "Acme Roof Inspection", '
            '"attribute": "service_area", "value": "Denver, CO", "status": "explicit", '
            '"evidence_excerpt": "Same-day inspections across Denver, CO.", '
            '"confidence": "high", "is_required_by_page_type": true}, '
            '{"eav_id": "eav-2", "entity_name": "Acme Roof Inspection", '
            '"attribute": "guarantee", "value": null, "status": "missing", '
            '"evidence_excerpt": null, "confidence": "high", '
            '"is_required_by_page_type": true}]}'
        ),
        why="Required keys present; the unsupported attribute is honestly marked 'missing'.",
    ),
    PromptExample(
        id="entities-incorrect",
        valid=False,
        user_fields={"content": "Page text.", "page_url": "https://example.com/x"},
        output=(
            '{"entities": [{"entity_id": "ent-1", "canonical_name": "Acme"}], '
            '"eav_rows": [{"eav_id": "eav-1", "entity_name": "Acme", '
            '"attribute": "guarantee", "value": "Lifetime warranty", '
            '"evidence_excerpt": null}]}'
        ),
        why=(
            "The 'guarantee' row omits its required 'status' key, and the value it does "
            "assert ('Lifetime warranty') appears nowhere on the page — a fabrication the "
            "schema forces the model to classify honestly."
        ),
    ),
]
