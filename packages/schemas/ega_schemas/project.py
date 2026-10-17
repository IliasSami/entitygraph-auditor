"""Project, SiteProfile, and workspace schemas (PRD §10, FR-01)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SiteProfile(BaseModel):
    """Domain and site-level entity profile."""

    site_name: str
    canonical_domain: str
    brand_entity: str
    primary_locale: str = "en"
    description: Optional[str] = None
    social_profiles: list[str] = Field(default_factory=list)


class ProjectCreate(BaseModel):
    """Payload to create or update an auditing project."""

    name: str
    brand: Optional[str] = None
    base_url: Optional[str] = None
    languages: list[str] = Field(default_factory=lambda: ["en"])
    country_region: Optional[str] = None
    target_market: Optional[str] = None
    industry: Optional[str] = None
    audience_icp: Optional[str] = None
    central_entity: Optional[str] = None
    target_conversion: Optional[str] = None
    model_profile: str = "local_default"
    context_pack_ids: list[str] = Field(default_factory=list)
    source_connectors: list[str] = Field(default_factory=list)
    archived: bool = False


class ProjectRead(ProjectCreate):
    """Project record returned by API."""

    project_id: str
    created_at: str
    updated_at: str
    audit_count: int = 0


class ContextPackSummary(BaseModel):
    """Summary of imported context pack."""

    pack_id: str
    name: str
    version: str = "1.0.0"
    version_hash: str = ""
    imported_at: str = ""
    source_file: Optional[str] = None
    scope: str = "project"
    document_count: int = 0
    rule_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)

