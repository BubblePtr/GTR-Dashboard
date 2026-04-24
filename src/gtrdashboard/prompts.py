"""Prompt template loader.

Loads agent prompts from external .md files in the prompts/ directory.
Supports runtime hot-loading for rapid iteration.
"""

from pathlib import Path

# Prompts directory — adjacent to project root
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


def load_prompt(agent_name: str, prompt_type: str = "system") -> str:
    """Load a prompt template from file.

    Args:
        agent_name: Agent identifier (collector, profiler, strategist, curator)
        prompt_type: Prompt type (system or user)

    Returns:
        Prompt text

    Raises:
        FileNotFoundError: If prompt file doesn't exist
    """
    file_path = PROMPTS_DIR / f"{agent_name}_{prompt_type}.md"
    if not file_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {file_path}")
    return file_path.read_text(encoding="utf-8")


def load_collector_prompt() -> str:
    """Load TrendingCollector system prompt."""
    return load_prompt("collector", "system")


def load_profiler_prompt() -> str:
    """Load ProjectProfiler system prompt."""
    return load_prompt("profiler", "system")


def load_strategist_prompt() -> str:
    """Load ContentStrategist system prompt."""
    return load_prompt("strategist", "system")


def load_curator_prompt() -> str:
    """Load CuratorAgent system prompt."""
    return load_prompt("curator", "system")


def load_reviewer_prompt() -> str:
    """Load TopicReviewerAgent system prompt."""
    return load_prompt("topic_reviewer", "system")
