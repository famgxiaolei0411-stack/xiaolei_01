"""Orchestration for skill selection, prompt composition, and review."""

from __future__ import annotations

from typing import Any

from skills.core.base import BaseSkill
from skills.core.context import SkillContext
from skills.core.registry import SkillRegistry
from skills.core.result import PromptFragment, SkillIssue, SkillResult
from skills.core.selector import SkillSelector


class SkillOrchestrator:
    """Coordinate selected skills without external side effects."""

    def __init__(self, registry: SkillRegistry) -> None:
        self._selector = SkillSelector(registry)

    def select(self, context: SkillContext) -> list[BaseSkill]:
        """Select applicable skills for the context."""

        return self._selector.select(context)

    def compose_prompt(self, base_prompt: str, context: SkillContext) -> str:
        """Append selected skill prompt fragments to a base prompt."""

        fragments: list[PromptFragment] = []
        for skill in self.select(context):
            fragments.extend(skill.contribute_prompt(context))

        if not fragments:
            return base_prompt

        ordered = sorted(
            fragments,
            key=lambda fragment: (fragment.priority, fragment.skill_id, fragment.title),
        )
        sections = [base_prompt.rstrip()]
        for fragment in ordered:
            sections.append(f"## {fragment.title}\n{fragment.content.strip()}")
        return "\n\n".join(section for section in sections if section)

    def review_output(self, context: SkillContext, output: Any) -> SkillResult:
        """Aggregate review results from selected skills."""

        issues: list[SkillIssue] = []
        suggestions: list[str] = []
        metrics: dict[str, Any] = {}
        metadata: dict[str, Any] = {"skills": []}

        for skill in self.select(context):
            result = skill.review_output(context, output)
            issues.extend(result.issues)
            suggestions.extend(result.suggestions)
            if result.metrics:
                metrics[skill.skill_id] = dict(result.metrics)
            if result.metadata:
                metadata[skill.skill_id] = dict(result.metadata)
            metadata["skills"].append(skill.skill_id)

        return SkillResult(
            skill_id="orchestrator",
            issues=tuple(issues),
            suggestions=tuple(suggestions),
            metrics=metrics,
            metadata=metadata,
        )
