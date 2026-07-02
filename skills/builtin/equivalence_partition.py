"""Equivalence partitioning skill."""

from __future__ import annotations

from skills.core.base import BaseSkill, SkillMetadata
from skills.core.context import SkillContext
from skills.core.result import PromptFragment


class EquivalencePartitionSkill(BaseSkill):
    """Contribute equivalence partitioning guidance to generation prompts."""

    metadata = SkillMetadata(
        skill_id="equivalence_partition",
        name="Equivalence Partitioning",
        description="Guide test design toward valid and invalid input classes.",
        stages=("testpoint_generation", "testcase_generation"),
        priority=30,
        metadata={
            "technique": "equivalence_partitioning",
            "category": "test_design",
        },
    )

    def contribute_prompt(self, context: SkillContext) -> list[PromptFragment]:
        """Return equivalence partitioning guidance for applicable stages."""

        if not self.can_apply(context):
            return []

        content = "\n".join([
            "请应用等价类划分补充测试设计，重点覆盖：",
            "1. 有效等价类：满足输入约束和业务规则的典型数据",
            "2. 无效等价类：不满足输入约束、格式、范围或业务规则的数据",
            "3. 输入类型：文本、数字、金额、日期、枚举、文件、布尔值等不同类型",
            "4. 业务规则分类：权限、状态、唯一性、必填项、依赖关系、互斥关系",
            "输出时说明等价类代表的数据或条件，避免只写“有效/无效输入”。",
        ])

        return [
            PromptFragment(
                skill_id=self.skill_id,
                title="等价类划分",
                content=content,
                priority=self.priority,
                metadata={
                    "stage": context.stage,
                    "technique": "equivalence_partitioning",
                },
            )
        ]
