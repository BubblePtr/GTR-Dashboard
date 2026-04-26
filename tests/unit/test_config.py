"""Tests for environment loading."""

from __future__ import annotations

import os

from gtrdashboard.config import load_project_env


def test_load_project_env_reads_dotenv_without_overriding_existing_values(
    tmp_path,
    monkeypatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "GTR_TEST_ENV_LOADED=from-dotenv\n"
        "GTR_TEST_ENV_EXISTING=from-dotenv\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("GTR_TEST_ENV_LOADED", raising=False)
    monkeypatch.setenv("GTR_TEST_ENV_EXISTING", "from-shell")

    loaded = load_project_env(env_path)

    assert loaded is True
    assert os.getenv("GTR_TEST_ENV_LOADED") == "from-dotenv"
    assert os.getenv("GTR_TEST_ENV_EXISTING") == "from-shell"
