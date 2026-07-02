"""Pure data context passed to skills."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class SkillContext:
    """Context available to skills during selection and execution.

    The context intentionally contains plain Python data only. It must not
    carry ORM objects, request objects, database sessions, or AI clients.
    """

    stage: str
    mode: str = "auto"
    feature_name: str = ""
    feature_description: str = ""
    document_text: str = ""
    testpoints: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    testcases: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=dict)
