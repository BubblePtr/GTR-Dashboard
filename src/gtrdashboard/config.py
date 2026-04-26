"""Shared runtime configuration helpers."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def load_project_env(env_path: Path | None = None) -> bool:
    """Load project-level dotenv variables without overriding shell-provided values."""
    path = env_path or PROJECT_ROOT / ".env"
    if not path.exists():
        return False
    return load_dotenv(path, override=False)
