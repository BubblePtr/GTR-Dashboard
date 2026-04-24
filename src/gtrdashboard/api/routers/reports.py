"""Reports router."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/reports", tags=["reports"])

REPORTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "reports"


@router.get("")
def list_reports() -> list[str]:
    """List available report dates."""
    if not REPORTS_DIR.exists():
        return []
    reports = sorted(REPORTS_DIR.glob("daily_report_*.md"), reverse=True)
    return [r.stem.replace("daily_report_", "") for r in reports]


@router.get("/{date}", response_class=PlainTextResponse)
def get_report(date: str) -> str:
    """Get a report by date (YYYY-MM-DD)."""
    report_path = REPORTS_DIR / f"daily_report_{date}.md"
    if not report_path.exists():
        return "Report not found"
    return report_path.read_text(encoding="utf-8")
