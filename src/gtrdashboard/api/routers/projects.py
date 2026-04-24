"""Projects router."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from gtrdashboard.api.deps import get_db
from gtrdashboard.api.schemas import ProjectOut
from gtrdashboard.models import RawProject

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db),
    language: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[RawProject]:
    """List collected projects with optional filtering."""
    query = select(RawProject).order_by(RawProject.collected_at.desc())
    if language:
        query = query.where(RawProject.language == language)
    projects = db.exec(query.offset(offset).limit(limit)).all()
    return list(projects)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, db: Session = Depends(get_db)) -> RawProject:
    """Get a single project by ID."""
    project = db.get(RawProject, project_id)
    if not project:
        raise Exception("Project not found")
    return project
