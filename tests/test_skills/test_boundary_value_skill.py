"""Tests for the boundary value skill."""

from __future__ import annotations

from skills.builtin.boundary_value import BoundaryValueSkill
from skills.core.context import SkillContext


def test_boundary_value_skill_metadata() -> None:
    skill = BoundaryValueSkill()

    assert skill.skill_id == "boundary_value"
    assert skill.metadata.name == "Boundary Value Analysis"
    assert skill.metadata.priority == 20
    assert skill.metadata.stages == ("testpoint_generation", "testcase_generation")
    assert skill.metadata.metadata["technique"] == "boundary_value_analysis"


def test_boundary_value_skill_applies_to_generation_stages() -> None:
    skill = BoundaryValueSkill()

    assert skill.can_apply(SkillContext(stage="testpoint_generation"))
    assert skill.can_apply(SkillContext(stage="testcase_generation"))
    assert not skill.can_apply(SkillContext(stage="quality_review"))


def test_boundary_value_skill_contributes_prompt_fragment() -> None:
    skill = BoundaryValueSkill()

    fragments = skill.contribute_prompt(
        SkillContext(
            stage="testpoint_generation",
            feature_name="用户登录",
            feature_description="用户输入账号密码登录系统",
        )
    )

    assert len(fragments) == 1
    fragment = fragments[0]
    assert fragment.skill_id == "boundary_value"
    assert fragment.title == "边界值分析"
    assert fragment.priority == 20
    assert "空值" in fragment.content
    assert "最小值" in fragment.content
    assert "最大值" in fragment.content
    assert "边界前一个值" in fragment.content
    assert fragment.metadata["stage"] == "testpoint_generation"


def test_boundary_value_skill_does_not_contribute_when_not_applicable() -> None:
    skill = BoundaryValueSkill()

    fragments = skill.contribute_prompt(SkillContext(stage="quality_review"))

    assert fragments == []


def test_boundary_value_skill_review_is_empty_by_default() -> None:
    skill = BoundaryValueSkill()

    result = skill.review_output(
        SkillContext(stage="testpoint_generation"),
        output={"testpoints": []},
    )

    assert result.skill_id == "boundary_value"
    assert result.issues == ()
    assert result.suggestions == ()
    assert result.metrics == {}
