"""Prompt for the gate node (PRD §8.10, §23) — the quality gate.

Reviews the assembled run against the configured checklist and returns a verdict. The
verdict must reflect the checks as they actually went; a gate that passes everything
because it looked at nothing is worse than no gate.
"""

from __future__ import annotations

from auditor.prompts._shared import GUARDRAILS, PromptExample

#: Registry key for this prompt.
NAME = "gate"
#: Graph node this prompt is wired to (shared QA gate; used by the critic pass).
WORKFLOW_NODE = None
#: Semantic version — bump on any wording or schema change.
PROMPT_VERSION = "1.0.0"
#: One-line description for the UI / prompt inspector.
SUMMARY = "Rule on the assembled run against the configured checklist and list what failed."

SYSTEM = (
    "You are the Quality Gate for EntityGraph Auditor.\n"
    "You are handed the assembled result of an audit run and a checklist. For each\n"
    "check you decide pass / pass_with_fixes / fail on the evidence in front of you,\n"
    "then give an overall verdict. You do not soften a verdict to keep the run green,\n"
    "and you never claim a check was performed when the run did not perform it.\n"
    "\n"
    "Your reply MUST be a single JSON object matching this JSON Schema:\n"
    "{schema_json}\n"
    "\n"
    + GUARDRAILS
)

USER_TEMPLATE = """Rule on this audit run.

<untrusted_content>
{run_summary}
</untrusted_content>

Configured checklist:
{checklist}

Context:
- page_url: {page_url}
- central_entity: {central_entity}

Return only JSON matching the provided schema.
"""

OUTPUT_SCHEMA: dict[str, object] = {
    "type": "object",
    "required": ["gate_status", "issues"],
    "properties": {
        "gate_status": {
            "type": "string",
            "enum": ["pass", "pass_with_fixes", "fail", "not_configured", "not_assessed"],
        },
        "issues": {"type": "array", "items": {"type": "string"}},
        "failed_checks": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": ["string", "null"]},
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low", "not_assessed"],
        },
    },
}

EXAMPLES: list[PromptExample] = [
    PromptExample(
        id="gate-correct",
        valid=True,
        user_fields={
            "run_summary": '{"nodes": {"claims": {"status": "ok"}, "critic": {"approved": false}}}',
            "checklist": "- [ ] every claim has a verification state\n- [ ] critic approved",
            "page_url": "https://example.com/roof-inspection",
            "central_entity": "Acme Roof Inspection",
        },
        output=(
            '{"gate_status": "fail", "issues": ["Critic rejected the run: 2 unresolved issues."], '
            '"failed_checks": ["critic approved"], '
            '"notes": "Claims stage completed; critic did not approve.", '
            '"confidence": "high"}'
        ),
        why="The verdict follows the evidence: the critic rejected, so the gate fails.",
    ),
    PromptExample(
        id="gate-incorrect",
        valid=False,
        user_fields={"run_summary": "{}", "checklist": "- [ ] unknown"},
        output='{"gate_status": "pass", "issues": "none"}',
        why=(
            "'issues' is a string rather than an array of strings, so the failing checks "
            "cannot be enumerated — and a gate that reports no issues from an empty run "
            "summary has passed something it never inspected."
        ),
    ),
]
