"""Agent 6 — Evidence / Claim Verification Agent (PRD §8.2)."""

from __future__ import annotations

import time
from typing import Any

from ega_providers.registry import ProviderRegistry
from ega_schemas.audit import AuditRunState
from ega_schemas.claims import Claim
from ega_schemas.providers import ModelCallRequest

from auditor.prompts.templates import CLAIMS_AGENT_PROMPT


def run_claims_agent(state: AuditRunState) -> dict[str, Any]:
    """Identify empirical claims and evaluate required citations."""
    start = time.time()
    provider = ProviderRegistry.get_provider(state.model_provider, state.model_name)

    user_prompt = f"""Content to analyze for empirical claims and citations:
<untrusted_content>
{state.content[:4000]}
</untrusted_content>
"""
    req = ModelCallRequest(
        system_prompt=CLAIMS_AGENT_PROMPT,
        user_prompt=user_prompt,
    )
    res = provider.call(req)
    parsed = res.parsed_json or {}

    claims: list[Claim] = []
    for c in parsed.get("claims", []):
        try:
            claims.append(Claim.model_validate(c))
        except Exception:
            pass

    elapsed = int((time.time() - start) * 1000)
    timeline_entry = {
        "node": "claims_agent",
        "duration_ms": elapsed,
        "claim_count": len(claims),
    }

    current_timeline = list(state.timeline)
    current_timeline.append(timeline_entry)

    return {
        "claims": claims,
        "timeline": current_timeline,
    }
