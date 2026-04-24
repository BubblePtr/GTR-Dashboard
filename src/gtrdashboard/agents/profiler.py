"""ProjectProfilerAgent — analyzes GitHub repositories with LLM.

Data flow:
    RawProject + README text
        → format as input string
        → OpenAI chat.completions.create with JSON prompt
        → ProjectProfile

Failure modes:
    - LLM API error → skip project, log error
    - Invalid response format → retry once, then degrade
    - README missing → degrade to metadata-only analysis
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field

from gtrdashboard.models import ProjectProfile, RawProject
from gtrdashboard.prompts import load_profiler_prompt


class ProfilerOutput(BaseModel):
    """Structured output from ProjectProfilerAgent."""

    novelty_score: int = Field(ge=1, le=10)
    utility_score: int = Field(ge=1, le=10)
    doc_quality_score: int = Field(ge=1, le=10)
    local_ai_relevance: int = Field(ge=1, le=10)
    tags: list[str] = Field(default_factory=list)
    summary: str = Field(default="")


@dataclass
class ProfilerConfig:
    """Configuration for ProjectProfiler."""

    positioning: str = "本地AI实战派"
    model: str = "qwen3.6-max-preview"
    max_retries: int = 1


class ProjectProfilerAgent:
    """Analyzes GitHub repositories and produces structured assessments."""

    def __init__(self, config: Optional[ProfilerConfig] = None) -> None:
        self.config = config or ProfilerConfig()
        # Lazy-init client to avoid import-time side effects
        self._client: Optional[object] = None

    def _get_client(self) -> object:
        """Return an OpenAI client configured from env."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                base_url=os.getenv("OPENAI_BASE_URL"),
            )
        return self._client

    async def analyze(
        self,
        project: RawProject,
        readme_text: Optional[str] = None,
    ) -> ProjectProfile:
        """Analyze a single project.

        Args:
            project: Raw project data
            readme_text: README content (may be None or truncated)

        Returns:
            ProjectProfile with analysis scores
        """
        context = self._build_context(project, readme_text)
        system_prompt = load_profiler_prompt()
        system_prompt = system_prompt.replace("{{ positioning }}", self.config.positioning)

        # Append JSON schema reminder to ensure consistent output
        schema_hint = (
            "\n\nYou MUST return ONLY a single valid JSON object matching this schema:\n"
            + json.dumps(ProfilerOutput.model_json_schema(), indent=2)
            + "\nDo not wrap in markdown code blocks."
        )
        system_prompt += schema_hint

        client = self._get_client()

        for attempt in range(self.config.max_retries + 1):
            try:
                response = await asyncio.to_thread(
                    client.chat.completions.create,
                    model=self.config.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": context},
                    ],
                    temperature=0.3,
                )
                text = response.choices[0].message.content.strip()
                # Strip markdown fences if present
                if text.startswith("```"):
                    text = text.strip("`").strip()
                    if text.lower().startswith("json"):
                        text = text[4:].strip()
                data = json.loads(text)
                output = ProfilerOutput(**data)

                return ProjectProfile(
                    raw_project_id=project.id,
                    novelty_score=output.novelty_score,
                    utility_score=output.utility_score,
                    doc_quality_score=output.doc_quality_score,
                    local_ai_relevance=output.local_ai_relevance,
                    tags=json.dumps(output.tags) if output.tags else "[]",
                    summary=output.summary,
                    analysis_status="complete",
                )
            except Exception as e:
                print(f"[Profiler] Attempt {attempt + 1} failed for {project.name}: {e}")
                if attempt == self.config.max_retries:
                    break
                # Brief pause before retry
                await asyncio.sleep(0.5)

        return self._degraded_profile(project, f"LLM analysis failed after retries")

    def _build_context(self, project: RawProject, readme_text: Optional[str]) -> str:
        """Format project data as input for the LLM."""
        lines = [
            f"Repository: {project.owner}/{project.name}",
            f"URL: {project.github_url}",
            f"Language: {project.language or 'Unknown'}",
            f"Stars: {project.stars or 'N/A'}",
            f"Description: {project.description or 'N/A'}",
            "",
        ]

        if readme_text:
            lines.append("README Content:")
            lines.append(readme_text[:5000])  # Limit context size
            lines.append("")
        else:
            lines.append("README: Not available (analysis based on metadata only)")
            lines.append("")

        lines.append("Please analyze this repository and return your assessment as JSON.")
        return "\n".join(lines)

    def _degraded_profile(self, project: RawProject, reason: str) -> ProjectProfile:
        """Create a degraded profile when LLM analysis fails.

        Uses heuristics based on metadata to produce conservative scores.
        """
        stars = project.stars or 0

        # Heuristic scoring based on stars
        novelty = 5 if stars > 1000 else 4
        utility = 6 if stars > 500 else 5
        doc_quality = 3  # Can't assess docs without README
        local_ai = 5  # Neutral without analysis

        summary = f"{project.name}：{project.description or '暂无描述'}"
        if len(summary) > 200:
            summary = summary[:197] + "..."

        return ProjectProfile(
            raw_project_id=project.id,
            novelty_score=novelty,
            utility_score=utility,
            doc_quality_score=doc_quality,
            local_ai_relevance=local_ai,
            tags=json.dumps(["uncategorized"]),
            summary=summary,
            analysis_status="degraded",
            analysis_reason=f"LLM analysis failed: {reason}",
        )
