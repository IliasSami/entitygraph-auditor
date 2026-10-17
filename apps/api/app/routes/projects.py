"""Project endpoints (FR-01)."""

from __future__ import annotations

from ega_api.db import get_db
from ega_api.errors import ApiError
from ega_api.models import AuditLog, Project
from ega_schemas.project import ProjectCreate, ProjectRead
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_read(p: Project) -> ProjectRead:
    return ProjectRead(
        project_id=p.project_id,
        name=p.name,
        brand=p.brand,
        base_url=p.base_url,
        languages=p.languages or ["en"],
        country_region=p.country_region,
        target_market=p.target_market,
        industry=p.industry,
        audience_icp=p.audience_icp,
        central_entity=p.central_entity,
        target_conversion=p.target_conversion,
        model_profile=p.model_profile,
        context_pack_ids=p.context_pack_ids or [],
        source_connectors=p.source_connectors or [],
        archived=p.archived,
        created_at=p.created_at.isoformat(),
        updated_at=p.updated_at.isoformat(),
    )


@router.post("", response_model=ProjectRead, status_code=201)
def create_project(payload: ProjectCreate, session: Session = Depends(get_db)) -> ProjectRead:
    project = Project(**payload.model_dump())
    session.add(project)
    session.add(AuditLog(action="project.create", target=payload.name))
    session.commit()
    session.refresh(project)
    return _to_read(project)


@router.get("", response_model=list[ProjectRead])
def list_projects(
    include_archived: bool = False, session: Session = Depends(get_db)
) -> list[ProjectRead]:
    q = session.query(Project)
    if not include_archived:
        q = q.filter(Project.archived.is_(False))
    return [_to_read(p) for p in q.order_by(Project.created_at.desc()).all()]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project_id: str, session: Session = Depends(get_db)) -> ProjectRead:
    project = session.get(Project, project_id)
    if project is None:
        raise ApiError("PROJECT_NOT_FOUND", f"Project {project_id} not found", 404)
    return _to_read(project)


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str, payload: ProjectCreate, session: Session = Depends(get_db)
) -> ProjectRead:
    project = session.get(Project, project_id)
    if project is None:
        raise ApiError("PROJECT_NOT_FOUND", f"Project {project_id} not found", 404)
    for k, v in payload.model_dump().items():
        setattr(project, k, v)
    session.commit()
    session.refresh(project)
    return _to_read(project)


@router.post("/{project_id}/archive", response_model=ProjectRead)
def archive_project(project_id: str, session: Session = Depends(get_db)) -> ProjectRead:
    project = session.get(Project, project_id)
    if project is None:
        raise ApiError("PROJECT_NOT_FOUND", f"Project {project_id} not found", 404)
    project.archived = True
    session.add(AuditLog(action="project.archive", target=project_id))
    session.commit()
    return _to_read(project)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, session: Session = Depends(get_db)) -> None:
    """Hard delete (PRD FR-24 data deletion). Cascades content versions and audits."""
    project = session.get(Project, project_id)
    if project is None:
        raise ApiError("PROJECT_NOT_FOUND", f"Project {project_id} not found", 404)
    session.delete(project)
    session.add(AuditLog(action="project.delete", target=project_id))
    session.commit()
