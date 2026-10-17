"""Workspace read-model endpoints: Entity Hub, Brief Builder, content analysis.

These back the Aentio UI screens with deterministic, provenance-labelled data
derived from stored audits and context packs (FR-16/FR-18/PRD §8). No model
provider is required, so they work in deterministic-only mode.
"""

from __future__ import annotations

from ega_api.db import get_db
from ega_api.services.workspace import (
    analyze_content,
    build_entity_registry,
    generate_brief,
)
from ega_schemas.workspace import (
    AnalyzeRequest,
    AnalyzeResponse,
    BriefGenerateRequest,
    BriefResponse,
    WorkspaceEntitiesResponse,
)
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/entities", response_model=WorkspaceEntitiesResponse)
def list_entities(
    project_id: str = Query(..., description="Project whose knowledge registry to read"),
    session: Session = Depends(get_db),
) -> WorkspaceEntitiesResponse:
    """Entity registry derived from this project's successful audits + packs."""
    return build_entity_registry(session, project_id)


@router.post("/briefs/generate", response_model=BriefResponse)
def generate_brief_endpoint(
    payload: BriefGenerateRequest, session: Session = Depends(get_db)
) -> BriefResponse:
    """Assemble a writer brief from real coverage queries, findings and facts."""
    return generate_brief(session, payload)


@router.post("/analyze", response_model=AnalyzeResponse)
def analyze_content_endpoint(payload: AnalyzeRequest) -> AnalyzeResponse:
    """Deterministic editorial analysis of a draft (readability, structure, terms)."""
    return analyze_content(payload)
