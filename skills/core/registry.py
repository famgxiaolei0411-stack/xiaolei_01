"""In-memory skill registry."""

from __future__ import annotations

from collections import OrderedDict

from skills.core.base import BaseSkill
from skills.core.exceptions import SkillNotFoundError, SkillRegistrationError


class SkillRegistry:
    """Register and retrieve skill instances."""

    def __init__(self) -> None:
        self._skills: OrderedDict[str, BaseSkill] = OrderedDict()

    def register(self, skill: BaseSkill) -> None:
        """Register a skill instance by its stable id."""

        skill_id = skill.skill_id.strip()
        if not skill_id:
            raise SkillRegistrationError("Skill id cannot be empty")
        if skill_id in self._skills:
            raise SkillRegistrationError(f"Skill already registered: {skill_id}")
        self._skills[skill_id] = skill

    def get(self, skill_id: str) -> BaseSkill:
        """Return a registered skill by id."""

        try:
            return self._skills[skill_id]
        except KeyError as exc:
            raise SkillNotFoundError(f"Skill not found: {skill_id}") from exc

    def all(self) -> list[BaseSkill]:
        """Return all registered skills in registration order."""

        return list(self._skills.values())

    def __contains__(self, skill_id: str) -> bool:
        return skill_id in self._skills

    def __len__(self) -> int:
        return len(self._skills)
