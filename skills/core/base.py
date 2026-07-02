"""Base skill abstractions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from skills.core.context import SkillContext
from skills.core.result import PromptFragment, SkillResult


@dataclass(frozen=True)
class SkillMetadata:
    """Static metadata describing a skill."""

    skill_id: str
    name: str
    description: str = ""
    stages: Sequence[str] = field(default_factory=tuple)
    priority: int = 100
    metadata: Mapping[str, Any] = field(default_factory=dict)


class BaseSkill:
    """Base class for pure, pluggable testing skills.

    Subclasses can override any method. The default implementation is empty
    and side-effect free, which keeps new skills simple to test.
    """

    metadata = SkillMetadata(
        skill_id="base",
        name="Base Skill",
        description="Default no-op skill.",
    )

    @property
    def skill_id(self) -> str:
        """Stable identifier for the skill."""

        return self.metadata.skill_id

    @property
    def priority(self) -> int:
        """Lower values run earlier."""

        return self.metadata.priority

    def can_apply(self, context: SkillContext) -> bool:
        """Return whether this skill applies to the current context."""

        if not self.metadata.stages:
            return False
        return context.stage in self.metadata.stages

    def contribute_prompt(self, context: SkillContext) -> list[PromptFragment]:
        """Return prompt fragments contributed by this skill."""

        return []

    def review_output(
        self,
        context: SkillContext,
        output: Any,
    ) -> SkillResult:
        """Review generated output and return structured feedback."""

        return SkillResult.empty(self.skill_id)
