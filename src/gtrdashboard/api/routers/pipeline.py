"""Pipeline router."""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlmodel import Session

from gtrdashboard.api.deps import get_db
from gtrdashboard.api.schemas import PipelineRunConfig, PipelineRunResponse, PipelineRunStatus
from gtrdashboard.database import create_pipeline_run, get_pipeline_stages, get_session
from gtrdashboard.models import PipelineRun
from gtrdashboard.pipeline import PipelineConfig, PipelineOrchestrator

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

# In-memory registry of running tasks
_running_tasks: dict[int, asyncio.Task] = {}


@router.post("/run", response_model=PipelineRunResponse)
async def run_pipeline(
    config: PipelineRunConfig,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> PipelineRunResponse:
    """Trigger a new pipeline run in the background."""
    # Create run record first so frontend can poll immediately
    run = create_pipeline_run(db)

    # Build domain config from API schema
    domain_config = PipelineConfig(
        languages=config.languages,
        limit=config.limit,
        fetch_readme=config.fetch_readme,
        profile_concurrency=config.profile_concurrency,
        top_n=config.top_n,
        source=config.source,
        model=config.model,
    )

    # Start pipeline in background
    task = asyncio.create_task(_execute_pipeline(run.id, domain_config))
    _running_tasks[run.id] = task

    return PipelineRunResponse(run_id=run.id, status="running")


async def _execute_pipeline(run_id: int, config: PipelineConfig) -> None:
    """Background task that executes the pipeline."""
    try:
        orchestrator = PipelineOrchestrator(config)
        await orchestrator.run(existing_run_id=run_id, triggered_by="api")
    except Exception as e:
        print(f"[API Pipeline] Run {run_id} failed: {e}")
    finally:
        _running_tasks.pop(run_id, None)
        try:
            await orchestrator.primary_collector.close()
            if orchestrator.exa_collector:
                await orchestrator.exa_collector.close()
        except NameError:
            pass


@router.get("/status/{run_id}", response_model=PipelineRunStatus)
def get_pipeline_status(run_id: int, db: Session = Depends(get_db)) -> PipelineRunStatus:
    """Get the current status of a pipeline run."""
    run = db.get(PipelineRun, run_id)
    if not run:
        raise Exception("Pipeline run not found")

    stages = get_pipeline_stages(db, run_id)
    stage_outs = [
        {
            "id": s.id,
            "stage_name": s.stage_name,
            "status": s.status,
            "progress": s.progress,
            "message": s.message,
            "started_at": s.started_at,
            "finished_at": s.finished_at,
        }
        for s in stages
    ]

    return PipelineRunStatus(
        id=run.id,
        status=run.status,
        projects_collected=run.projects_collected,
        projects_analyzed=run.projects_analyzed,
        topics_generated=run.topics_generated,
        triggered_by=run.triggered_by,
        started_at=run.started_at,
        finished_at=run.finished_at,
        stages=stage_outs,
        error_log=run.error_log,
    )


@router.get("/runs", response_model=list[PipelineRunStatus])
def list_pipeline_runs(
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
) -> list[PipelineRunStatus]:
    """List historical pipeline runs."""
    from sqlmodel import select

    runs = db.exec(
        select(PipelineRun).order_by(PipelineRun.started_at.desc()).offset(offset).limit(limit)
    ).all()

    result: list[PipelineRunStatus] = []
    for run in runs:
        stages = get_pipeline_stages(db, run.id)
        stage_outs = [
            {
                "id": s.id,
                "stage_name": s.stage_name,
                "status": s.status,
                "progress": s.progress,
                "message": s.message,
                "started_at": s.started_at,
                "finished_at": s.finished_at,
            }
            for s in stages
        ]
        result.append(
            PipelineRunStatus(
                id=run.id,
                status=run.status,
                projects_collected=run.projects_collected,
                projects_analyzed=run.projects_analyzed,
                topics_generated=run.topics_generated,
                triggered_by=run.triggered_by,
                started_at=run.started_at,
                finished_at=run.finished_at,
                stages=stage_outs,
                error_log=run.error_log,
            )
        )
    return result
