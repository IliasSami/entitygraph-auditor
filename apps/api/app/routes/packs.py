"""Context / skill pack endpoints (FR-16)."""

from __future__ import annotations

import uuid
from typing import Any

from ega_api.db import get_db
from ega_api.errors import ApiError
from ega_api.models import AuditLog, ContextPack, ContextPackVersion
from ega_schemas.project import ContextPackSummary
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

router = APIRouter(prefix="/context-packs", tags=["context-packs"])


def _summary(pack: ContextPack) -> ContextPackSummary:
    return ContextPackSummary(
        pack_id=pack.pack_id,
        name=pack.name,
        version=pack.version,
        version_hash=pack.version_hash,
        imported_at=pack.created_at.isoformat(),
        source_file=pack.source_file,
        scope=pack.scope,
        document_count=pack.document_count,
        rule_count=pack.rule_count,
        warnings=pack.warnings or [],
        conflicts=pack.conflicts or [],
        files=pack.files or [],
    )


@router.post("/import", status_code=201)
async def import_pack_endpoint(
    request: Request, session: Session = Depends(get_db)
) -> ContextPackSummary:
    ctype = (request.headers.get("content-type") or "").lower()
    if not ctype.startswith("multipart/form-data"):
        raise ApiError("INVALID_BODY", "multipart/form-data with a 'file' field is required", 422)
    form = await request.form()
    upload = form.get("file")
    if upload is None or not hasattr(upload, "read"):
        raise ApiError("MISSING_FILE", "multipart request must include a 'file' field", 422)
    data: bytes = await upload.read()
    filename = getattr(upload, "filename", None) or "pack.zip"

    try:
        from ega_api.services.packs import import_pack  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover
        raise ApiError("IMPORTER_UNAVAILABLE", f"Pack importer unavailable: {exc}", 503) from exc
    try:
        parsed = import_pack(data, filename)
    except ValueError as exc:
        raise ApiError("PACK_REJECTED", str(exc)[:400], 422) from exc

    pack = ContextPack(
        name=parsed.name,
        version=parsed.version,
        version_hash=parsed.version_hash,
        source_file=parsed.source_file,
        manifest=parsed.manifest,
        files=parsed.files,
        warnings=parsed.warnings,
        conflicts=parsed.conflicts,
        document_count=len(parsed.documents),
        rule_count=(
            len(parsed.brand_rules)
            + len(parsed.canonical_facts)
            + len(parsed.banned_terms)
            + len(parsed.approved_claims)
            + len(parsed.topical_map_rows)
            + len(parsed.internal_link_targets)
        ),
    )
    session.add(pack)
    session.flush()
    session.add(
        ContextPackVersion(
            pack_id=pack.pack_id,
            version=pack.version,
            version_hash=pack.version_hash,
            payload={
                "brand_rules": parsed.brand_rules,
                "canonical_facts": parsed.canonical_facts,
                "banned_terms": parsed.banned_terms,
                "approved_claims": parsed.approved_claims,
                "topical_map_rows": parsed.topical_map_rows,
                "internal_link_targets": parsed.internal_link_targets,
                "scoring_config": parsed.scoring_config,
                "documents": [
                    {k: d.get(k) for k in ("path", "kind", "sha256")} for d in parsed.documents
                ],
                "writer_handoff_template": parsed.writer_handoff_template,
                "scripts": parsed.scripts,
            },
        )
    )
    session.add(AuditLog(action="pack.import", target=parsed.name, detail={"files": len(parsed.files)}))
    session.commit()
    session.refresh(pack)
    return _summary(pack)


@router.get("", response_model=list[ContextPackSummary])
def list_packs(session: Session = Depends(get_db)) -> list[ContextPackSummary]:
    packs = session.query(ContextPack).order_by(ContextPack.created_at.desc()).all()
    summaries = [_summary(p) for p in packs]
    from auditor.context_packs import get_builtin_packs  # noqa: PLC0415

    for bp in get_builtin_packs():
        pid = bp.get("pack_id", "")
        if not any(s.pack_id == pid for s in summaries):
            summaries.append(
                ContextPackSummary(
                    pack_id=pid,
                    name=bp.get("name", "Built-in Pack"),
                    version=bp.get("version", "1.0.0"),
                    version_hash="builtin",
                    imported_at="",
                    source_file="builtin",
                    scope=bp.get("scope", "general"),
                    document_count=len(bp.get("documents", [])),
                    rule_count=len(bp.get("brand_rules", [])) + len(bp.get("banned_terms", [])),
                    warnings=[],
                    conflicts=[],
                    files=[],
                )
            )
    return summaries


@router.get("/{pack_id}")
def get_pack(pack_id: str, session: Session = Depends(get_db)) -> dict:
    pack = session.get(ContextPack, pack_id)
    if pack is None:
        from auditor.context_packs import get_builtin_pack  # noqa: PLC0415

        builtin = get_builtin_pack(pack_id)
        if builtin is not None:
            return {
                "pack_id": builtin.get("pack_id", pack_id),
                "name": builtin.get("name", "Built-in Pack"),
                "version": builtin.get("version", "1.0.0"),
                "version_hash": "builtin",
                "imported_at": "",
                "source_file": "builtin",
                "scope": builtin.get("scope", "general"),
                "document_count": 0,
                "rule_count": len(builtin.get("brand_rules", [])) + len(builtin.get("banned_terms", [])),
                "warnings": [],
                "conflicts": [],
                "files": [],
                "manifest": {"description": builtin.get("description", "")},
                "payload_summary": _payload_summary(builtin),
                "payload": builtin,
            }
        raise ApiError("PACK_NOT_FOUND", f"Context pack {pack_id} not found", 404)
    latest = (
        session.query(ContextPackVersion)
        .filter(ContextPackVersion.pack_id == pack_id)
        .order_by(ContextPackVersion.id.desc())
        .first()
    )
    latest_payload = latest.payload if latest else {}
    return {
        **_summary(pack).model_dump(mode="json"),
        "manifest": pack.manifest,
        "payload_summary": _payload_summary(latest_payload),
        "payload": latest_payload,
    }


@router.post("/{pack_id}/facts", status_code=201)
def add_pack_fact(pack_id: str, fact_data: dict, session: Session = Depends(get_db)) -> dict:
    pack = session.get(ContextPack, pack_id)
    if pack is None:
        raise ApiError("PACK_NOT_FOUND", f"Context pack {pack_id} not found", 404)
    latest = (
        session.query(ContextPackVersion)
        .filter(ContextPackVersion.pack_id == pack_id)
        .order_by(ContextPackVersion.id.desc())
        .first()
    )
    if not latest:
        raise ApiError("PACK_VERSION_MISSING", f"No version record found for pack {pack_id}", 404)

    payload = dict(latest.payload or {})
    facts = list(payload.get("canonical_facts") or [])
    new_fact = {
        "key": fact_data.get("key") or fact_data.get("property") or "fact",
        "value": fact_data.get("value") or "",
        "source": fact_data.get("source") or "Manual Verification",
        "verified": True,
    }
    facts.append(new_fact)
    payload["canonical_facts"] = facts
    latest.payload = payload
    pack.rule_count = (pack.rule_count or 0) + 1
    session.add(AuditLog(action="pack.add_fact", target=pack_id, detail={"fact": new_fact["key"]}))
    session.commit()
    return {"success": True, "fact": new_fact, "total_facts": len(facts)}


@router.post("/{pack_id}/entities", status_code=201)
def add_pack_entity(pack_id: str, entity_data: dict, session: Session = Depends(get_db)) -> dict:
    pack = session.get(ContextPack, pack_id)
    if pack is None:
        raise ApiError("PACK_NOT_FOUND", f"Context pack {pack_id} not found", 404)
    latest = (
        session.query(ContextPackVersion)
        .filter(ContextPackVersion.pack_id == pack_id)
        .order_by(ContextPackVersion.id.desc())
        .first()
    )
    if not latest:
        raise ApiError("PACK_VERSION_MISSING", f"No version record found for pack {pack_id}", 404)

    payload = dict(latest.payload or {})
    entities = list(payload.get("entities") or [])
    name_slug = entity_data.get("name", "entity").lower().replace(" ", "-")
    new_entity = {
        "id": entity_data.get("id") or f"ent-{uuid.uuid4().hex[:6]}",
        "canonical_id": entity_data.get("canonical_id") or f"#{name_slug}",
        "name": entity_data.get("name") or "New Entity",
        "type": entity_data.get("type") or "Organization",
        "definition": entity_data.get("definition") or "",
        "at_id": entity_data.get("at_id") or f"https://example.com/#{name_slug}",
        "schema_type": entity_data.get("schema_type") or "schema.org/Thing",
    }
    entities.append(new_entity)
    payload["entities"] = entities
    latest.payload = payload
    session.add(AuditLog(action="pack.add_entity", target=pack_id, detail={"entity": new_entity["name"]}))
    session.commit()
    return {"success": True, "entity": new_entity, "total_entities": len(entities)}


@router.get("/{pack_id}/schema-jsonld")
def export_schema_jsonld(pack_id: str, session: Session = Depends(get_db)) -> dict:
    pack_data = get_pack(pack_id, session)
    payload = pack_data.get("payload") or {}
    facts = payload.get("canonical_facts") or []
    entities = payload.get("entities") or []
    name = pack_data.get("name") or "Organization"

    graph = []
    main_node: dict[str, Any] = {
        "@type": "Organization",
        "@id": f"https://schema.org/{pack_id}#entity",
        "name": name,
        "description": pack_data.get("manifest", {}).get("description") or f"Grounded Entity Profile for {name}",
    }
    for f in facts:
        if isinstance(f, dict):
            k = f.get("key") or f.get("property") or ""
            v = f.get("value") or ""
            if k and v:
                main_node[k] = v

    graph.append(main_node)

    for ent in entities:
        graph.append({
            "@type": ent.get("type", "Thing"),
            "@id": ent.get("at_id") or ent.get("canonical_id"),
            "name": ent.get("name"),
            "description": ent.get("definition"),
        })

    return {
        "@context": "https://schema.org",
        "@graph": graph,
    }



def _payload_summary(payload: dict) -> dict:
    return {
        "brand_rules": len(payload.get("brand_rules") or []),
        "canonical_facts": len(payload.get("canonical_facts") or []),
        "banned_terms": len(payload.get("banned_terms") or []),
        "approved_claims": len(payload.get("approved_claims") or []),
        "topical_map_rows": len(payload.get("topical_map_rows") or []),
        "internal_link_targets": len(payload.get("internal_link_targets") or []),
        "documents": payload.get("documents") or [],
        "scripts_stored_not_executed": payload.get("scripts") or [],
    }


@router.delete("/{pack_id}", status_code=204)
def delete_pack(pack_id: str, session: Session = Depends(get_db)) -> None:
    pack = session.get(ContextPack, pack_id)
    if pack is None:
        raise ApiError("PACK_NOT_FOUND", f"Context pack {pack_id} not found", 404)
    session.delete(pack)
    session.add(AuditLog(action="pack.delete", target=pack_id))
    session.commit()
