"""History router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlmodel import Session, select

from gtrdashboard.api.deps import get_db
from gtrdashboard.api.schemas import HistoryPoint
from gtrdashboard.models import PipelineRun, TopicSuggestion

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[HistoryPoint])
def get_history(
    db: Session = Depends(get_db),
    days: int = Query(30, ge=1, le=365),
) -> list[HistoryPoint]:
    """Get historical pipeline summary for charting."""
    # Get pipeline runs with their topic counts
    runs = db.exec(
        select(PipelineRun)
        .where(PipelineRun.status.in_(["success", "partial_failure"]))
        .order_by(PipelineRun.started_at.desc())
        .limit(days)
    ).all()

    result: list[HistoryPoint] = []
    for run in runs:
        date_str = run.started_at.strftime("%Y-%m-%d")
        # Calculate average score of selected topics for this run
        # We approximate by looking at topics created on the same date
        avg_score = db.exec(
            select(func.avg(TopicSuggestion.final_score))
            .where(func.date(TopicSuggestion.created_at) == date_str)
        ).one()

        result.append(
            HistoryPoint(
                date=date_str,
                avg_score=round(float(avg_score or 0), 2),
                total_projects=run.projects_collected,
                total_selected=run.topics_generated,
            )
        )

    return list(reversed(result))
