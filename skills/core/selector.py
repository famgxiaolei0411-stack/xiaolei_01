"""Skill selection logic."""

from __future__ import annotations

from skills.core.base import BaseSkill
from skills.core.context import SkillContext
from skills.core.registry import SkillRegistry


class SkillSelector:
    """Select applicable skills from a registry."""

    def __init__(self, registry: SkillRegistry) -> None:
        self._registry = registry

    def select(self, context: SkillContext) -> list[BaseSkill]:
        """Return skills that apply to the context, sorted by priority."""

        selected = [
            skill for skill in self._registry.all()
            if skill.can_apply(context)
        ]
        return sorted(selected, key=lambda skill: (skill.priority, skill.skill_id))
