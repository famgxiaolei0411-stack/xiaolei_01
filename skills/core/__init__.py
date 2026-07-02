"""Core abstractions for pluggable testing skills."""

from skills.core.base import BaseSkill, SkillMetadata
from skills.core.context import SkillContext
from skills.core.result import PromptFragment, SkillIssue, SkillResult

__all__ = [
    "BaseSkill",
    "PromptFragment",
    "SkillContext",
    "SkillIssue",
    "SkillMetadata",
    "SkillResult",
]
