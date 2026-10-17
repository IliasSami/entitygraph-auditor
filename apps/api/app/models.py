"""Relational models (PRD §10).

Normalization boundary (documented in DECISIONS.md):
- Relational tables for projects, context packs, content versions, provider/MCP
  configuration, score profiles, exports and audit logs — anything that is
  referenced, listed, authorized or edited.
- Audit artifact arrays (entities, EAV rows, triples, fan-out, claims, findings,
  scores, report) are stored as versioned JSON snapshot columns on
  `audit_runs` because a report is an immutable, reproducible snapshot keyed by
  content hash + profile version + pack versions + model + prompt versions.

Secrets are stored encrypted (Fernet) — never plaintext, never logged.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from ega_api.db import Base
from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


# ---------------------------------------------------------------- projects ---


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    languages: Mapped[list] = mapped_column(JSON, default=list)
    country_region: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_market: Mapped[str | None] = mapped_column(String(128), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    audience_icp: Mapped[str | None] = mapped_column(Text, nullable=True)
    central_entity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    target_conversion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_profile: Mapped[str] = mapped_column(String(64), default="local_default")
    context_pack_ids: Mapped[list] = mapped_column(JSON, default=list)
    source_connectors: Mapped[list] = mapped_column(JSON, default=list)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)

    content_versions: Mapped[list["ContentVersion"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    audits: Mapped[list["AuditRun"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


# ----------------------------------------------------------- context packs ---


class ContextPack(Base, TimestampMixin):
    __tablename__ = "context_packs"

    pack_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[str] = mapped_column(String(64), default="0.0.0")
    version_hash: Mapped[str] = mapped_column(String(64), default="")
    source_file: Mapped[str | None] = mapped_column(String(512), nullable=True)
    scope: Mapped[str] = mapped_column(String(64), default="project")
    manifest: Mapped[dict] = mapped_column(JSON, default=dict)
    files: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    conflicts: Mapped[list] = mapped_column(JSON, default=list)
    document_count: Mapped[int] = mapped_column(Integer, default=0)
    rule_count: Mapped[int] = mapped_column(Integer, default=0)

    versions: Mapped[list["ContextPackVersion"]] = relationship(
        back_populates="pack", cascade="all, delete-orphan"
    )


class ContextPackVersion(Base):
    """Immutable snapshot of an imported pack's parsed payload."""

    __tablename__ = "context_pack_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pack_id: Mapped[str] = mapped_column(ForeignKey("context_packs.pack_id", ondelete="CASCADE"))
    version: Mapped[str] = mapped_column(String(64))
    version_hash: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # rules/facts/claims/rows
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    pack: Mapped[ContextPack] = relationship(back_populates="versions")


# ---------------------------------------------------------------- content ---


class ContentSource(Base, TimestampMixin):
    __tablename__ = "content_sources"

    source_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    kind: Mapped[str] = mapped_column(String(32))  # paste | upload | url | sitemap | duplicate
    original_format: Mapped[str] = mapped_column(String(32), default="text")
    filename: Mapped[str | None] = mapped_column(String(512), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    fetched_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    http_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    render_mode: Mapped[str] = mapped_column(String(32), default="text_only")
    parser: Mapped[str] = mapped_column(String(32), default="text")
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extraction_notes: Mapped[list] = mapped_column(JSON, default=list)
    limitations: Mapped[list] = mapped_column(JSON, default=list)


class ContentVersion(Base, TimestampMixin):
    __tablename__ = "content_versions"

    content_version_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.project_id", ondelete="SET NULL"), nullable=True
    )
    source_id: Mapped[str | None] = mapped_column(
        ForeignKey("content_sources.source_id", ondelete="SET NULL"), nullable=True
    )
    content_hash: Mapped[str] = mapped_column(String(80), index=True)
    original_format: Mapped[str] = mapped_column(String(32), default="text")
    original_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text)
    document: Mapped[dict] = mapped_column(JSON, default=dict)  # ParsedDocument snapshot

    project: Mapped[Project | None] = relationship(back_populates="content_versions")
    source: Mapped[ContentSource | None] = relationship()


# ----------------------------------------------------------------- audits ---


class AuditRun(Base, TimestampMixin):
    __tablename__ = "audit_runs"

    audit_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.project_id", ondelete="SET NULL"), nullable=True
    )
    content_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("content_versions.content_version_id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    # 'queued' | 'running' | 'succeeded' | 'failed'
    request: Mapped[dict] = mapped_column(JSON, default=dict)  # AuditCreateRequest snapshot
    stages: Mapped[list] = mapped_column(JSON, default=list)  # StageRecord list
    error: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # summary columns for list views (no need to deserialize the whole report)
    page_type: Mapped[str | None] = mapped_column(String(48), nullable=True)
    language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    central_entity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    primary_query: Mapped[str | None] = mapped_column(String(512), nullable=True)
    gate_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    composite: Mapped[float | None] = mapped_column(Float, nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(80), nullable=True)
    score_profile: Mapped[str | None] = mapped_column(String(64), nullable=True)
    score_profile_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    provider_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    context_pack_versions: Mapped[list] = mapped_column(JSON, default=list)
    deterministic_only: Mapped[bool] = mapped_column(Boolean, default=False)
    depth: Mapped[str] = mapped_column(String(16), default="standard")

    # immutable report snapshot
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    report_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # alias kept for exports

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    project: Mapped[Project | None] = relationship(back_populates="audits")
    agent_runs: Mapped[list["AuditAgentRun"]] = relationship(
        back_populates="audit", cascade="all, delete-orphan"
    )


class AuditAgentRun(Base):
    __tablename__ = "audit_agent_runs"
    __table_args__ = (UniqueConstraint("audit_id", "node", name="uq_audit_node"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(ForeignKey("audit_runs.audit_id", ondelete="CASCADE"))
    node: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    origin: Mapped[str] = mapped_column(String(24), default="deterministic")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    retries: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_estimated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cached: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    audit: Mapped[AuditRun] = relationship(back_populates="agent_runs")


# ---------------------------------------------------------- configuration ---


class ModelProviderConfig(Base, TimestampMixin):
    __tablename__ = "model_provider_configs"

    config_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    label: Mapped[str] = mapped_column(String(128))
    provider_type: Mapped[str] = mapped_column(String(32))  # ollama|openai_compatible|openai|anthropic|gemini|null
    base_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    api_key_env: Mapped[str | None] = mapped_column(String(128), nullable=True)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)  # Fernet token
    timeout_s: Mapped[int] = mapped_column(Integer, default=60)
    max_tokens: Mapped[int] = mapped_column(Integer, default=2048)
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class McpServerConfig(Base, TimestampMixin):
    __tablename__ = "mcp_server_configs"

    server_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(128))
    transport: Mapped[str] = mapped_column(String(16), default="http")  # http | stdio
    endpoint: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    command: Mapped[list | None] = mapped_column(JSON, nullable=True)  # stdio argv
    allowed_tools: Mapped[list] = mapped_column(JSON, default=list)
    timeout_s: Mapped[int] = mapped_column(Integer, default=30)
    auth_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_tools: Mapped[list] = mapped_column(JSON, default=list)


class ScoreProfile(Base, TimestampMixin):
    __tablename__ = "score_profiles"

    profile_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    version: Mapped[str] = mapped_column(String(32), default="1.0")
    preset: Mapped[str] = mapped_column(String(32), default="commercial")
    weights: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReportExport(Base, TimestampMixin):
    __tablename__ = "report_exports"

    export_id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    audit_id: Mapped[str] = mapped_column(ForeignKey("audit_runs.audit_id", ondelete="CASCADE"))
    fmt: Mapped[str] = mapped_column(String(16))
    filename: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


class AuditLog(Base):
    """Settings/model/provider/export/MCP activity (PRD FR-24)."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    action: Mapped[str] = mapped_column(String(64), index=True)  # settings.change | provider.test | export | mcp.call | pack.import | audit.create ...
    actor: Mapped[str] = mapped_column(String(64), default="local")
    target: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)  # redacted payloads only
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)


class CacheEntry(Base):
    """Project-isolated intermediate-result cache (PRD §8.5).

    Key = sha256(content_hash + page-type settings + pack versions + provider/
    model + agent prompt versions). Never shared across projects.
    """

    __tablename__ = "cache_entries"
    __table_args__ = (UniqueConstraint("project_id", "cache_key", name="uq_project_cache"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(32), index=True)
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    node: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    hits: Mapped[int] = mapped_column(Integer, default=0)


__all__ = [
    "AuditAgentRun",
    "CacheEntry",
    "AuditLog",
    "AuditRun",
    "ContentSource",
    "ContentVersion",
    "ContextPack",
    "ContextPackVersion",
    "McpServerConfig",
    "ModelProviderConfig",
    "Project",
    "ReportExport",
    "ScoreProfile",
    "TimestampMixin",
]
