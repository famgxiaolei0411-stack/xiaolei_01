"""Tests for the equivalence partitioning skill."""

from __future__ import annotations

from skills.builtin.equivalence_partition import EquivalencePartitionSkill
from skills.core.context import SkillContext


def test_equivalence_partition_skill_metadata() -> None:
    skill = EquivalencePartitionSkill()

    assert skill.skill_id == "equivalence_partition"
    assert skill.metadata.name == "Equivalence Partitioning"
    assert skill.metadata.priority == 30
    assert skill.metadata.stages == ("testpoint_generation", "testcase_generation")
    assert skill.metadata.metadata["technique"] == "equivalence_partitioning"


def test_equivalence_partition_skill_applies_to_generation_stages() -> None:
    skill = EquivalencePartitionSkill()

    assert skill.can_apply(SkillContext(stage="testpoint_generation"))
    assert skill.can_apply(SkillContext(stage="testcase_generation"))
    assert not skill.can_apply(SkillContext(stage="quality_review"))


def test_equivalence_partition_skill_contributes_prompt_fragment() -> None:
    skill = EquivalencePartitionSkill()

    fragments = skill.contribute_prompt(
        SkillContext(
            stage="testpoint_generation",
            feature_name="用户注册",
            feature_description="用户通过手机号或邮箱注册账号",
        )
    )

    assert len(fragments) == 1
    fragment = fragments[0]
    assert fragment.skill_id == "equivalence_partition"
    assert fragment.title == "等价类划分"
    assert fragment.priority == 30
    assert "有效等价类" in fragment.content
    assert "无效等价类" in fragment.content
    assert "输入类型" in fragment.content
    assert "业务规则" in fragment.content
    assert fragment.metadata["stage"] == "testpoint_generation"


def test_equivalence_partition_skill_does_not_contribute_when_not_applicable() -> None:
    skill = EquivalencePartitionSkill()

    fragments = skill.contribute_prompt(SkillContext(stage="quality_review"))

    assert fragments == []


def test_equivalence_partition_skill_review_is_empty_by_default() -> None:
    skill = EquivalencePartitionSkill()

    result = skill.review_output(
        SkillContext(stage="testpoint_generation"),
        output={"testpoints": []},
    )

    assert result.skill_id == "equivalence_partition"
    assert result.issues == ()
    assert result.suggestions == ()
    assert result.metrics == {}
