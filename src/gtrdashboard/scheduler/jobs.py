"""Scheduled job definitions."""

from __future__ import annotations

from gtrdashboard.pipeline import PipelineConfig, PipelineOrchestrator


async def run_scheduled_pipeline() -> None:
    """Run the pipeline on schedule."""
    config = PipelineConfig()
    orchestrator = PipelineOrchestrator(config)
    try:
        await orchestrator.run(triggered_by="scheduled")
    except Exception as e:
        print(f"[Scheduler] Pipeline failed: {e}")
    finally:
        await orchestrator.primary_collector.close()
        if orchestrator.exa_collector:
            await orchestrator.exa_collector.close()
