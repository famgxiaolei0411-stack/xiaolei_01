"""Boundary value analysis skill."""

from __future__ import annotations

from skills.core.base import BaseSkill, SkillMetadata
from skills.core.context import SkillContext
from skills.core.result import PromptFragment


class BoundaryValueSkill(BaseSkill):
    """Contribute boundary value analysis guidance to generation prompts."""

    metadata = SkillMetadata(
        skill_id="boundary_value",
        name="Boundary Value Analysis",
        description="Guide test design toward minimum, maximum, empty, and off-by-one values.",
        stages=("testpoint_generation", "testcase_generation"),
        priority=20,
        metadata={
            "technique": "boundary_value_analysis",
            "category": "test_design",
        },
    )

    def contribute_prompt(self, context: SkillContext) -> list[PromptFragment]:
        """Return boundary value prompt guidance for applicable stages."""

        if not self.can_apply(context):
            return []

        content = "\n".join([
            "请应用边界值分析补充测试设计，重点覆盖：",
            "1. 空值、缺失值、默认值",
            "2. 最小值、最大值、刚好等于边界",
            "3. 边界前一个值、边界后一个值",
            "4. 超长输入、超出范围输入、非法格式输入",
            "5. 数量、金额、长度、时间、分页、状态码等字段的临界场景",
            "输出时保持具体、可验证，避免只写“边界值测试”这类笼统描述。",
        ])

        return [
            PromptFragment(
                skill_id=self.skill_id,
                title="边界值分析",
                content=content,
                priority=self.priority,
                metadata={
                    "stage": context.stage,
                    "technique": "boundary_value_analysis",
                },
            )
        ]
