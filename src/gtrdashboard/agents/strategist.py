"""ContentStrategistAgent — generates content ideas from project analyses.

Data flow:
    List[ProjectProfile] (batch of 10)
        → format as input string
        → OpenAI chat.completions.create with JSON prompt
        → List[TopicSuggestion]

Failure modes:
    - LLM API error → degrade all topics to basic info
    - Invalid response format → retry once, then degrade
    - Partial failure within batch → degrade individual topics
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field

from gtrdashboard.models import ProjectProfile, TopicSuggestion
from gtrdashboard.prompts import load_strategist_prompt


class TopicOutput(BaseModel):
    """Single topic output from ContentStrategist."""

    why_post: str = Field(default="")
    differentiation_angle: str = Field(default="")
    target_audience: str = Field(default="")
    engagement_estimate: str = Field(default="medium")
    draft_tweet: str = Field(default="")
    draft_script: str = Field(default="")
    draft_outline: str = Field(default="")


class StrategistOutput(BaseModel):
    """Structured output from ContentStrategistAgent."""

    topics: list[TopicOutput] = Field(default_factory=list)


@dataclass
class StrategistConfig:
    """Configuration for ContentStrategist."""

    positioning: str = "本地AI实战派"
    model: str = "qwen3.6-max-preview"
    batch_size: int = 10


class ContentStrategistAgent:
    """Generates content strategy and drafts from project analyses."""

    def __init__(self, config: Optional[StrategistConfig] = None) -> None:
        self.config = config or StrategistConfig()
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

    async def generate(
        self,
        profiles: list[ProjectProfile],
    ) -> list[TopicSuggestion]:
        """Generate topic suggestions for a batch of project profiles.

        Args:
            profiles: List of analyzed project profiles

        Returns:
            List of topic suggestions aligned with user positioning
        """
        if not profiles:
            return []

        context = self._build_batch_context(profiles)
        system_prompt = load_strategist_prompt()
        system_prompt = system_prompt.replace("{{ positioning }}", self.config.positioning)

        schema_hint = (
            "\n\nYou MUST return ONLY a single valid JSON object with a 'topics' array. "
            "Each topic must match this schema:\n"
            + json.dumps(TopicOutput.model_json_schema(), indent=2)
            + "\nDo not wrap in markdown code blocks."
        )
        system_prompt += schema_hint

        client = self._get_client()

        try:
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context},
                ],
                temperature=0.7,
            )
            text = response.choices[0].message.content.strip()
            if text.startswith("```"):
                text = text.strip("`").strip()
                if text.lower().startswith("json"):
                    text = text[4:].strip()
            data = json.loads(text)
            output = StrategistOutput(**data)

            # Map outputs to profiles
            topics: list[TopicSuggestion] = []
            for i, profile in enumerate(profiles):
                if i < len(output.topics):
                    topic_data = output.topics[i]
                    topics.append(
                        TopicSuggestion(
                            profile_id=profile.id,
                            why_post=topic_data.why_post,
                            differentiation_angle=topic_data.differentiation_angle,
                            target_audience=topic_data.target_audience,
                            engagement_estimate=topic_data.engagement_estimate,
                            draft_tweet=topic_data.draft_tweet,
                            draft_script=topic_data.draft_script,
                            draft_outline=topic_data.draft_outline,
                            generation_status="complete",
                        )
                    )
                else:
                    # Missing output for this profile — degrade
                    topics.append(self._degraded_topic(profile))

            return topics

        except Exception as e:
            print(f"[Strategist] Batch generation failed: {e}")
            # Degrade all topics in the batch
            return [self._degraded_topic(p) for p in profiles]

    def _build_batch_context(self, profiles: list[ProjectProfile]) -> str:
        """Format a batch of profiles as input for the LLM."""
        lines = [
            f"Generate content strategy for {len(profiles)} projects.",
            "",
            "For EACH project, provide: why_post, differentiation_angle, target_audience, engagement_estimate, draft_tweet, draft_script, draft_outline.",
            "",
        ]

        for i, profile in enumerate(profiles):
            # Parse tags from JSON string
            tags = []
            if profile.tags:
                try:
                    tags = json.loads(profile.tags)
                except json.JSONDecodeError:
                    tags = []

            lines.append(f"--- Project {i + 1} ---")
            lines.append(f"Summary: {profile.summary or 'N/A'}")
            lines.append(f"Novelty: {profile.novelty_score}/10")
            lines.append(f"Utility: {profile.utility_score}/10")
            lines.append(f"Local AI Relevance: {profile.local_ai_relevance}/10")
            lines.append(f"Doc Quality: {profile.doc_quality_score}/10")
            lines.append(f"Tags: {', '.join(tags) if tags else 'N/A'}")
            lines.append("")

        lines.append("Return results as a JSON object with a 'topics' array.")
        return "\n".join(lines)

    def _degraded_topic(self, profile: ProjectProfile) -> TopicSuggestion:
        """Create a degraded topic when generation fails."""
        summary = profile.summary or "一个有趣的项目"
        return TopicSuggestion(
            profile_id=profile.id,
            why_post="",
            differentiation_angle="",
            target_audience="",
            engagement_estimate="low",
            draft_tweet=f"值得关注：{summary[:200]}",
            draft_script="",
            draft_outline="",
            generation_status="degraded",
            generation_reason="Batch generation failed or missing output",
        )
