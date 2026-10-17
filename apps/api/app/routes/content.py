"""Content ingestion endpoints (FR-02, FR-23).

Import parses immediately with the deterministic parser and stores an
immutable ContentVersion snapshot (original text, normalized text, parse tree).
"""

from __future__ import annotations

from ega_api.config import Settings, get_settings
from ega_api.db import get_db
from ega_api.errors import ApiError
from ega_api.models import AuditLog, ContentSource, ContentVersion
from ega_schemas.content import ContentSourceMeta
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

router = APIRouter(prefix="/content", tags=["content"])

FORMAT_BY_EXT = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".html": "html",
    ".htm": "html",
    ".txt": "text",
    ".docx": "docx",
    ".pdf": "pdf",
}


def _parse(text: str, fmt: str, source: ContentSourceMeta):
    try:
        from ega_parsers import parse_content  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover
        raise ApiError("PARSER_UNAVAILABLE", f"Deterministic parser unavailable: {exc}", 503) from exc
    try:
        return parse_content(text, content_format=fmt, source=source)
    except ValueError as exc:
        raise ApiError("PARSE_FAILED", str(exc)[:400], 422) from exc


def _persist(
    session: Session, project_id: str | None, doc, meta: ContentSourceMeta
) -> ContentVersion:
    src = ContentSource(
        kind=meta.kind,
        original_format=meta.original_format,
        filename=meta.filename,
        url=meta.url,
        fetched_at=meta.fetched_at,
        http_status=meta.http_status,
        canonical_url=meta.canonical_url,
        render_mode=meta.render_mode,
        parser=meta.parser,
        size_bytes=meta.size_bytes,
        extraction_notes=meta.extraction_notes,
        limitations=meta.limitations,
    )
    session.add(src)
    session.flush()
    version = ContentVersion(
        project_id=project_id,
        source_id=src.source_id,
        content_hash=doc.content_hash,
        original_format=meta.original_format,
        original_text=doc.original_text,
        normalized_text=doc.normalized_text,
        document=doc.model_dump(mode="json"),
    )
    session.add(version)
    session.add(AuditLog(action="content.import", target=meta.filename or meta.kind))
    session.commit()
    session.refresh(version)
    return version


def _summary(doc) -> dict:
    stats = getattr(doc, "stats", None)
    word_count = stats.word_count if stats else getattr(doc, "word_count", 0)
    char_count = stats.char_count if stats else getattr(doc, "char_count", 0)
    h1 = getattr(doc, "h1", None)
    if not h1 and getattr(doc, "headings", None):
        h1_nodes = [h.text for h in doc.headings if getattr(h, "level", 0) == 1]
        h1 = h1_nodes[0] if h1_nodes else None
    source = getattr(doc, "source", None)
    notes = (getattr(source, "extraction_notes", None) or []) + (getattr(source, "limitations", None) or []) if source else []

    return {
        "word_count": word_count,
        "char_count": char_count,
        "headings": len(getattr(doc, "headings", [])),
        "sections": len(getattr(doc, "sections", [])),
        "passages": len(getattr(doc, "passages", [])),
        "language_hint": getattr(doc, "language_hint", "en"),
        "title": getattr(doc, "title", None),
        "h1": h1,
        "metadata_description": getattr(doc, "meta_description", None),
        "canonical_url": getattr(doc, "canonical_url", None),
        "suggested_page_type": getattr(doc, "suggested_page_type", None),
        "page_type_confidence": getattr(doc, "page_type_confidence", None),
        "page_type_rationale": getattr(doc, "page_type_rationale", None),
        "content_hash": getattr(doc, "content_hash", ""),
        "warnings": notes,
        "readability_warning": getattr(stats, "readability_warning", None) if stats else None,
    }



@router.post("/import")
async def import_content(
    request: Request,
    project_id: str | None = None,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Accepts either JSON {text, format, filename} or multipart file upload."""
    ctype = (request.headers.get("content-type") or "").lower()

    if ctype.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise ApiError("MISSING_FILE", "multipart request must include a 'file' field", 422)
        data: bytes = await upload.read()
        filename = getattr(upload, "filename", None) or "upload.txt"
        if len(data) > settings.max_upload_bytes:
            raise ApiError(
                "UPLOAD_TOO_LARGE",
                f"Upload exceeds {settings.max_upload_bytes} bytes",
                413,
            )
        meta = ContentSourceMeta(
            kind="upload",
            original_format=(_ext_format(filename)),
            filename=filename,
            size_bytes=len(data),
            parser="deterministic",
        )
        doc = _load_bytes(data, filename, meta)
    else:
        try:
            body = await request.json()
        except Exception as exc:
            raise ApiError("INVALID_BODY", "Expected JSON body or multipart upload", 422) from exc
        text = body.get("text") or body.get("content") or body.get("content_text") or ""
        fmt = (body.get("format") or body.get("content_format") or "markdown").lower()
        filename = body.get("filename")
        if not text.strip():
            raise ApiError("EMPTY_CONTENT", "Provide non-empty 'text'", 422)
        if len(text.encode("utf-8")) > settings.max_upload_bytes:
            raise ApiError("UPLOAD_TOO_LARGE", "Content exceeds upload limit", 413)
        meta = ContentSourceMeta(
            kind="paste", original_format=fmt, filename=filename, parser=f"{fmt}_parser"
        )
        doc = _parse(text, fmt, meta)

    version = _persist(session, project_id, doc, meta)
    chash = doc.content_hash if doc.content_hash.startswith("sha256:") else f"sha256:{doc.content_hash}"
    return {
        "content_version_id": version.content_version_id,
        "content_hash": chash,
        "document_summary": _summary(doc),
    }


@router.post("/fetch-url")
async def fetch_url_endpoint(
    payload: dict,
    project_id: str | None = None,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """SSRF-guarded URL fetch → parsed preview + optional stored ContentVersion."""
    url = (payload or {}).get("url")
    if not url:
        raise ApiError("MISSING_URL", "Provide 'url'", 422)
    store = bool((payload or {}).get("store", True))

    try:
        from ega_api.services.fetcher import FetchBlocked, fetch_url  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover
        raise ApiError("FETCHER_UNAVAILABLE", f"URL fetcher unavailable: {exc}", 503) from exc

    try:
        result = await fetch_url(
            url,
            allow_private=settings.allow_private_urls,
            timeout_s=settings.fetch_timeout_s,
            max_bytes=settings.max_fetch_bytes,
            respect_robots=settings.respect_robots,
        )
    except FetchBlocked as exc:
        code = getattr(exc, "code", "FETCH_BLOCKED")
        status = 451 if code == "ROBOTS_DISALLOWED" else 400
        raise ApiError(code, str(exc)[:300], status) from exc
    except Exception as exc:
        raise ApiError("FETCH_FAILED", f"Fetch failed: {type(exc).__name__}", 502) from exc

    meta = ContentSourceMeta(
        kind="url",
        original_format="html",
        url=url,
        fetched_at=result.fetched_at,
        http_status=result.status,
        canonical_url=result.canonical_url,
        render_mode=result.render_mode,
        parser="html_parser",
        size_bytes=result.size_bytes,
        limitations=list(result.limitations or []),
    )
    doc = _parse(result.body_text, "html", meta)
    if doc.meta_description is None and result.title:
        doc.title = doc.title or result.title
    response: dict = {
        "url": url,
        "final_url": result.final_url,
        "http_status": result.status,
        "content_type": result.content_type,
        "fetched_at": result.fetched_at,
        "canonical_url": result.canonical_url,
        "robots": result.robots,
        "limitations": result.limitations,
        "document_summary": _summary(doc),
    }
    if store:
        version = _persist(session, project_id, doc, meta)
        response["content_version_id"] = version.content_version_id
    return response


def _ext_format(filename: str) -> str:
    lowered = filename.lower()
    for ext, fmt in FORMAT_BY_EXT.items():
        if lowered.endswith(ext):
            return fmt
    return "text"


def _load_bytes(data: bytes, filename: str, meta: ContentSourceMeta):
    try:
        from ega_parsers import load_document_bytes  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover
        raise ApiError("PARSER_UNAVAILABLE", f"Document loader unavailable: {exc}", 503) from exc
    try:
        return load_document_bytes(data, filename, meta)
    except ValueError as exc:
        raise ApiError("PARSE_FAILED", str(exc)[:400], 422) from exc


class GenerateBriefRequest(BaseModel):
    target_query: str
    page_type: str = "service"
    project_id: str | None = None
    brand_name: str | None = None
    location: str | None = None
    context_pack_id: str | None = None


@router.post("/brief")
def create_content_brief(req: GenerateBriefRequest, session: Session = Depends(get_db)) -> dict:
    from ega_api.models import ContextPackVersion, Project  # noqa: PLC0415
    from ega_api.services.briefs import generate_content_brief  # noqa: PLC0415

    brand = req.brand_name
    loc = req.location
    pack_data: dict | None = None

    if req.project_id:
        proj = session.get(Project, req.project_id)
        if proj:
            brand = brand or proj.brand or proj.name
            loc = loc or proj.target_market

    if req.context_pack_id:
        v = (
            session.query(ContextPackVersion)
            .filter(ContextPackVersion.pack_id == req.context_pack_id)
            .order_by(ContextPackVersion.id.desc())
            .first()
        )
        if v and v.payload:
            pack_data = v.payload
        else:
            from auditor.context_packs import get_builtin_pack  # noqa: PLC0415

            bp = get_builtin_pack(req.context_pack_id)
            if bp:
                pack_data = bp

    return generate_content_brief(
        target_query=req.target_query,
        page_type=req.page_type,
        brand_name=brand,
        location=loc,
        context_pack_data=pack_data,
    )

