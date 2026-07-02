"""Tests for skill orchestration."""

from __future__ import annotations

from typing import Any

from skills.builtin.boundary_value import BoundaryValueSkill
from skills.core.base import BaseSkill, SkillMetadata
from skills.core.context import SkillContext
from skills.core.orchestrator import SkillOrchestrator
from skills.core.registry import SkillRegistry
from skills.core.result import PromptFragment, SkillIssue, SkillResult


class ReviewOnlySkill(BaseSkill):
    metadata = SkillMetadata(
        skill_id="review_only",
        name="Review Only",
        stages=("quality_review",),
        priority=10,
    )

    def review_output(self, context: SkillContext, output: Any) -> SkillResult:
        return SkillResult(
            skill_id=self.skill_id,
            issues=(
                SkillIssue(
                    skill_id=self.skill_id,
                    level="warning",
                    message="sample issue",
                ),
            ),
            suggestions=("sample suggestion",),
            metrics={"checked": True},
            metadata={"stage": context.stage},
        )


class PromptSkill(BaseSkill):
    metadata = SkillMetadata(
        skill_id="prompt_skill",
        name="Prompt Skill",
        stages=("testpoint_generation",),
        priority=5,
    )

    def contribute_prompt(self, context: SkillContext) -> list[PromptFragment]:
        return [
            PromptFragment(
                skill_id=self.skill_id,
                title="Prompt Skill",
                content="prompt fragment",
                priority=self.priority,
            )
        ]


def test_orchestrator_selects_applicable_skills_by_priority() -> None:
    registry = SkillRegistry()
    registry.register(BoundaryValueSkill())
    registry.register(PromptSkill())
    orchestrator = SkillOrchestrator(registry)

    selected = orchestrator.select(SkillContext(stage="testpoint_generation"))

    assert [skill.skill_id for skill in selected] == [
        "prompt_skill",
        "boundary_value",
    ]


def test_compose_prompt_appends_fragments() -> None:
    registry = SkillRegistry()
    registry.register(PromptSkill())
    orchestrator = SkillOrchestrator(registry)

    prompt = orchestrator.compose_prompt(
        "base prompt",
        SkillContext(stage="testpoint_generation"),
    )

    assert "base prompt" in prompt
    assert "## Prompt Skill" in prompt
    assert "prompt fragment" in prompt


def test_compose_prompt_returns_base_prompt_when_no_skill_applies() -> None:
    registry = SkillRegistry()
    registry.register(BoundaryValueSkill())
    orchestrator = SkillOrchestrator(registry)

    prompt = orchestrator.compose_prompt(
        "base prompt",
        SkillContext(stage="feature_extraction"),
    )

    assert prompt == "base prompt"


def test_review_output_aggregates_results() -> None:
    registry = SkillRegistry()
    registry.register(ReviewOnlySkill())
    orchestrator = SkillOrchestrator(registry)

    result = orchestrator.review_output(
        SkillContext(stage="quality_review"),
        output={"testcases": []},
    )

    assert result.skill_id == "orchestrator"
    assert len(result.issues) == 1
    assert result.issues[0].message == "sample issue"
    assert result.suggestions == ("sample suggestion",)
    assert result.metrics == {"review_only": {"checked": True}}
    assert result.metadata["skills"] == ["review_only"]


def test_review_output_returns_empty_result_when_no_skill_applies() -> None:
    registry = SkillRegistry()
    registry.register(BoundaryValueSkill())
    orchestrator = SkillOrchestrator(registry)

    result = orchestrator.review_output(
        SkillContext(stage="quality_review"),
        output={},
    )

    assert result.skill_id == "orchestrator"
    assert result.issues == ()
    assert result.suggestions == ()
    assert result.metrics == {}
    assert result.metadata == {"skills": []}
