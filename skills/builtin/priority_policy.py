"""Priority policy review skill."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from skills.core.base import BaseSkill, SkillMetadata
from skills.core.context import SkillContext
from skills.core.result import SkillIssue, SkillResult


VALID_PRIORITIES = {"P0", "P1", "P2", "P3", "P4"}
LOW_PRIORITY_FOR_HIGH_RISK = {"P3", "P4"}
HIGH_PRIORITY_FOR_LOW_RISK_UI = {"P0", "P1", "P2"}
P0_RATIO_THRESHOLD = 0.35

HIGH_RISK_KEYWORDS = (
    "登录",
    "支付",
    "权限",
    "资金",
    "订单",
    "删除",
    "数据丢失",
    "接口不可用",
    "认证",
    "授权",
    "安全",
)

UI_LOW_RISK_KEYWORDS = (
    "UI",
    "界面",
    "文案",
    "布局",
    "体验",
    "可读性",
    "颜色",
    "样式",
    "图标",
    "按钮文案",
    "提示语",
    "占位符",
    "对齐",
    "展示",
    "页面标题",
    "间距",
    "字体",
)


class PriorityPolicySkill(BaseSkill):
    """Review testcase priorities with local, testable policy rules."""

    metadata = SkillMetadata(
        skill_id="priority_policy",
        name="Priority Policy",
        description="Check testcase priority consistency against local risk rules.",
        stages=("quality_review",),
        priority=50,
        metadata={
            "technique": "priority_policy",
            "category": "quality_review",
        },
    )

    def review_output(
        self,
        context: SkillContext,
        output: Any,
    ) -> SkillResult:
        """Review priorities without mutating testcases or existing review."""

        testcases = list(context.testcases)
        checked = len(testcases)
        missing_priority = 0
        invalid_priority = 0
        p0_count = 0
        high_risk_low_priority = 0
        ui_low_risk_not_p4 = 0
        ui_low_risk_p4 = 0
        issues: list[SkillIssue] = []

        for index, testcase in enumerate(testcases, 1):
            case_id = str(
                testcase.get("case_id")
                or testcase.get("id")
                or f"#{index}"
            )
            priority = str(testcase.get("priority", "") or "").strip().upper()
            text = self._case_text(testcase)

            if not priority:
                missing_priority += 1
                issues.append(self._issue(
                    case_id,
                    "用例优先级缺失，建议按风险和影响范围补充 P0/P1/P2/P3/P4。",
                    rule="missing_priority",
                ))
                continue

            if priority not in VALID_PRIORITIES:
                invalid_priority += 1
                issues.append(self._issue(
                    case_id,
                    f"用例优先级不合法: {priority}，合法值为 P0/P1/P2/P3/P4。",
                    rule="invalid_priority",
                ))
                continue

            if priority == "P0":
                p0_count += 1

            is_high_risk = self._contains_any(text, HIGH_RISK_KEYWORDS)
            is_ui_low_risk = self._contains_any(text, UI_LOW_RISK_KEYWORDS)

            if is_high_risk and priority in LOW_PRIORITY_FOR_HIGH_RISK:
                high_risk_low_priority += 1
                issues.append(self._issue(
                    case_id,
                    "高风险用例优先级偏低，建议升为 P0/P1。",
                    rule="high_risk_low_priority",
                ))
                continue

            if is_ui_low_risk and not is_high_risk:
                if priority == "P4":
                    ui_low_risk_p4 += 1
                elif priority in HIGH_PRIORITY_FOR_LOW_RISK_UI:
                    ui_low_risk_not_p4 += 1
                    issues.append(self._issue(
                        case_id,
                        "UI / 文案 / 布局 / 体验 / 可读性类用例建议优先级设置为 P4。",
                        rule="ui_low_risk_not_p4",
                    ))

        p0_ratio = (p0_count / checked) if checked else 0
        p0_ratio_too_high = p0_ratio > P0_RATIO_THRESHOLD
        suggestions: list[str] = []
        if p0_ratio_too_high:
            issues.append(self._issue(
                "-",
                f"P0 占比 {p0_ratio:.0%} 偏高，建议仅保留阻塞级、核心链路和高风险场景。",
                rule="p0_ratio_too_high",
            ))
            suggestions.append("P0 用例占比偏高，建议重新区分阻塞级、核心链路、普通场景和低风险 UI 场景。")
        if ui_low_risk_not_p4:
            suggestions.append("UI、文案、布局、体验、可读性类检查建议统一沉淀为 P4。")
        if high_risk_low_priority:
            suggestions.append("登录、支付、权限、资金、订单、删除、安全等高风险场景建议优先使用 P0/P1。")

        metrics = {
            "checked": checked,
            "missing_priority": missing_priority,
            "invalid_priority": invalid_priority,
            "p0_count": p0_count,
            "p0_ratio": p0_ratio,
            "p0_ratio_too_high": p0_ratio_too_high,
            "high_risk_low_priority": high_risk_low_priority,
            "ui_low_risk_not_p4": ui_low_risk_not_p4,
            "ui_low_risk_p4": ui_low_risk_p4,
        }

        return SkillResult(
            skill_id=self.skill_id,
            issues=tuple(issues),
            suggestions=tuple(suggestions),
            metrics=metrics,
            metadata={"mode": context.mode},
        )

    @staticmethod
    def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
        lowered = text.lower()
        return any(keyword.lower() in lowered for keyword in keywords)

    @classmethod
    def _case_text(cls, testcase: Mapping[str, Any]) -> str:
        parts = [
            testcase.get("title", ""),
            testcase.get("expected", ""),
            testcase.get("expected_result", ""),
            testcase.get("precondition", ""),
            testcase.get("url", ""),
            testcase.get("method", ""),
            testcase.get("testpoint_description", ""),
        ]
        steps = testcase.get("steps", "")
        if isinstance(steps, list | tuple):
            parts.extend(steps)
        else:
            parts.append(steps)
        return " ".join(cls._stringify(part) for part in parts)

    @classmethod
    def _stringify(cls, value: Any) -> str:
        if isinstance(value, Mapping):
            return " ".join(f"{key} {cls._stringify(val)}" for key, val in value.items())
        if isinstance(value, list | tuple | set):
            return " ".join(cls._stringify(item) for item in value)
        return str(value or "")

    def _issue(
        self,
        case_id: str,
        message: str,
        *,
        rule: str,
        level: str = "warning",
    ) -> SkillIssue:
        return SkillIssue(
            skill_id=self.skill_id,
            level=level,
            target=case_id,
            message=message,
            metadata={"rule": rule},
        )
