"""Tests for skill registry behavior."""

from __future__ import annotations

import pytest

from skills.builtin.boundary_value import BoundaryValueSkill
from skills.core.base import BaseSkill, SkillMetadata
from skills.core.exceptions import SkillNotFoundError, SkillRegistrationError
from skills.core.registry import SkillRegistry


class EmptyIdSkill(BaseSkill):
    metadata = SkillMetadata(skill_id="", name="Empty")


def test_registry_registers_and_returns_skill() -> None:
    registry = SkillRegistry()
    skill = BoundaryValueSkill()

    registry.register(skill)

    assert len(registry) == 1
    assert "boundary_value" in registry
    assert registry.get("boundary_value") is skill
    assert registry.all() == [skill]


def test_registry_rejects_duplicate_skill_id() -> None:
    registry = SkillRegistry()
    registry.register(BoundaryValueSkill())

    with pytest.raises(SkillRegistrationError):
        registry.register(BoundaryValueSkill())


def test_registry_rejects_empty_skill_id() -> None:
    registry = SkillRegistry()

    with pytest.raises(SkillRegistrationError):
        registry.register(EmptyIdSkill())


def test_registry_raises_for_missing_skill() -> None:
    registry = SkillRegistry()

    with pytest.raises(SkillNotFoundError):
        registry.get("missing")
