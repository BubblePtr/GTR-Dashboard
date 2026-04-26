"""CLI entry point for GTR Dashboard.

Commands:
    gtr run          Execute the full pipeline
    gtr report       Show the latest report
    gtr config       Show/edit user preferences
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table

from gtrdashboard.config import load_project_env
from gtrdashboard.database import get_or_create_preferences, get_session, init_db
from gtrdashboard.pipeline import PipelineConfig, PipelineOrchestrator

load_project_env()

app = typer.Typer(
    name="gtr",
    help="GitHub Trending multi-agent content curation pipeline",
    no_args_is_help=True,
)
console = Console()

# Report directory (must match pipeline.py)
REPORTS_DIR = Path(__file__).parent.parent.parent / "reports"


@app.command()
def run(
    languages: list[str] | None = typer.Option(
        None, "--lang", help="Filter languages (default: python, typescript, go)"
    ),
    limit: int = typer.Option(50, "--limit", help="Max repos to collect"),
    fetch_readme: bool = typer.Option(True, "--readme/--no-readme", help="Fetch README content"),
    top_n: int = typer.Option(10, "--top-n", help="Number of topics to curate"),
    concurrency: int = typer.Option(3, "--concurrency", help="Max concurrent LLM calls"),
    source: str = typer.Option(
        "tavily",
        "--source",
        help="Data source: tavily | exa | both | legacy",
    ),
    exa_query: str | None = typer.Option(
        None, "--exa-query", help="Custom Exa semantic search query"
    ),
    model: str = typer.Option(
        "qwen3.6-max-preview",
        "--model",
        help="LLM model for profiler and strategist",
    ),
) -> None:
    """Execute the full curation pipeline."""
    config = PipelineConfig(
        languages=languages,
        limit=limit,
        fetch_readme=fetch_readme,
        profile_concurrency=concurrency,
        top_n=top_n,
        source=source,
        exa_query=exa_query,
        model=model,
    )
    orchestrator = PipelineOrchestrator(config)

    try:
        report, report_path = asyncio.run(orchestrator.run())
    except Exception as e:
        console.print(f"[red]Pipeline failed: {e}[/red]")
        raise typer.Exit(1)

    # Print summary
    table = Table(title=f"每日选题报告 — 共选出 {report.total_selected} 个选题")
    table.add_column("排名", justify="right", style="cyan")
    table.add_column("评分", justify="right", style="green")
    table.add_column("项目", style="white")
    table.add_column("地址", style="blue")
    table.add_column("入选原因", style="dim")

    for curated in report.topics:
        project_name = curated.project_name or "未知项目"
        if len(project_name) > 30:
            project_name = project_name[:27] + "..."
        project_url = curated.github_url or ""
        if len(project_url) > 45:
            project_url = project_url[:42] + "..."

        table.add_row(
            str(curated.rank),
            str(curated.final_score),
            project_name,
            project_url,
            curated.selection_reason,
        )

    console.print(table)
    console.print(f"\n[dim]完整报告已保存至: {report_path}[/dim]")


@app.command()
def report(
    date: str | None = typer.Option(None, "--date", help="Report date (YYYY-MM-DD)"),
) -> None:
    """Display the latest (or specified) daily report."""
    if date:
        report_path = REPORTS_DIR / f"daily_report_{date}.md"
    else:
        # Find most recent report
        if not REPORTS_DIR.exists():
            console.print("[red]暂无报告，请先运行 `gtr run`[/red]")
            raise typer.Exit(1)

        reports = sorted(REPORTS_DIR.glob("daily_report_*.md"), reverse=True)
        if not reports:
            console.print("[red]暂无报告，请先运行 `gtr run`[/red]")
            raise typer.Exit(1)
        report_path = reports[0]

    if not report_path.exists():
        console.print(f"[red]报告未找到: {report_path}[/red]")
        raise typer.Exit(1)

    content = report_path.read_text(encoding="utf-8")
    console.print(Markdown(content))


@app.command()
def config() -> None:
    """Show current user preferences."""
    init_db()
    session = get_session()
    prefs = get_or_create_preferences(session)
    session.close()

    table = Table(title="用户偏好设置")
    table.add_column("设置项", style="cyan")
    table.add_column("值", style="white")

    table.add_row("定位", prefs.positioning or "N/A")
    table.add_row("偏好语言", prefs.preferred_languages or "N/A")
    table.add_row("本地AI权重", str(prefs.local_ai_weight))
    table.add_row("最低星标数", str(prefs.min_stars_threshold))
    table.add_row("黑名单", prefs.blacklist_keywords or "[]")
    table.add_row("白名单", prefs.whitelist_keywords or "[]")

    console.print(table)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
