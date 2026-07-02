"""Exceptions raised by the skill infrastructure."""


class SkillError(Exception):
    """Base exception for skill infrastructure errors."""


class SkillRegistrationError(SkillError):
    """Raised when a skill cannot be registered."""


class SkillNotFoundError(SkillError):
    """Raised when a requested skill does not exist."""
