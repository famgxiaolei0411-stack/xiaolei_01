"""Structured outputs produced by skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class PromptFragment:
    """Prompt content contributed by a skill."""

    skill_id: str
    title: str
    content: str
    priority: int = 100
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillIssue:
    """A structured issue reported by a skill review."""

    skill_id: str
    level: str
    message: str
    target: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillResult:
    """Review result returned by a skill."""

    skill_id: str
    issues: tuple[SkillIssue, ...] = ()
    suggestions: tuple[str, ...] = ()
    metrics: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def empty(cls, skill_id: str) -> "SkillResult":
        """Return an empty result for a skill."""

        return cls(skill_id=skill_id)
