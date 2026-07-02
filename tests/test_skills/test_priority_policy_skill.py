"""Tests for the priority policy skill."""

from __future__ import annotations

from skills.builtin.priority_policy import PriorityPolicySkill, VALID_PRIORITIES
from skills.core.context import SkillContext


def _review(testcases: list[dict]) -> object:
    return PriorityPolicySkill().review_output(
        SkillContext(
            stage="quality_review",
            mode="functional",
            testcases=tuple(testcases),
        ),
        output={},
    )


def test_priority_policy_skill_metadata() -> None:
    skill = PriorityPolicySkill()

    assert skill.skill_id == "priority_policy"
    assert skill.metadata.name == "Priority Policy"
    assert skill.metadata.stages == ("quality_review",)
    assert VALID_PRIORITIES == {"P0", "P1", "P2", "P3", "P4"}


def test_missing_priority_produces_warning() -> None:
    result = _review([
        {"case_id": "TC-001", "title": "普通功能检查", "steps": ["操作"]},
    ])

    assert result.metrics["missing_priority"] == 1
    assert any(issue.metadata["rule"] == "missing_priority" for issue in result.issues)
    assert all(issue.level == "warning" for issue in result.issues)


def test_invalid_priority_produces_warning() -> None:
    result = _review([
        {"case_id": "TC-001", "title": "普通功能检查", "priority": "P9"},
    ])

    assert result.metrics["invalid_priority"] == 1
    assert any(issue.metadata["rule"] == "invalid_priority" for issue in result.issues)


def test_high_risk_p3_or_p4_suggests_p0_or_p1() -> None:
    result = _review([
        {"case_id": "TC-001", "title": "支付失败后资金回滚", "priority": "P3"},
        {"case_id": "TC-002", "title": "权限绕过检查", "priority": "P4"},
    ])

    assert result.metrics["high_risk_low_priority"] == 2
    messages = [issue.message for issue in result.issues]
    assert any("P0/P1" in message for message in messages)


def test_ui_low_risk_p0_p1_p2_suggests_p4() -> None:
    result = _review([
        {"case_id": "TC-001", "title": "按钮文案展示", "priority": "P0"},
        {"case_id": "TC-002", "title": "页面标题可读性", "priority": "P1"},
        {"case_id": "TC-003", "title": "布局间距检查", "priority": "P2"},
        {"case_id": "TC-004", "title": "图标颜色检查", "priority": "P4"},
    ])

    assert result.metrics["ui_low_risk_not_p4"] == 3
    assert result.metrics["ui_low_risk_p4"] == 1
    assert any("P4" in issue.message for issue in result.issues)


def test_high_risk_takes_precedence_over_ui_low_risk() -> None:
    result = _review([
        {"case_id": "TC-001", "title": "支付页面按钮文案错误导致无法提交订单", "priority": "P4"},
    ])

    assert result.metrics["high_risk_low_priority"] == 1
    assert result.metrics["ui_low_risk_not_p4"] == 0
    assert not any(issue.metadata["rule"] == "ui_low_risk_not_p4" for issue in result.issues)


def test_high_p0_ratio_produces_warning() -> None:
    result = _review([
        {"case_id": "TC-001", "title": "普通功能 A", "priority": "P0"},
        {"case_id": "TC-002", "title": "普通功能 B", "priority": "P0"},
        {"case_id": "TC-003", "title": "普通功能 C", "priority": "P2"},
    ])

    assert result.metrics["p0_count"] == 2
    assert result.metrics["p0_ratio"] == 2 / 3
    assert result.metrics["p0_ratio_too_high"] is True
    assert any(issue.metadata["rule"] == "p0_ratio_too_high" for issue in result.issues)


def test_metrics_include_required_fields_for_api_mode() -> None:
    skill = PriorityPolicySkill()

    result = skill.review_output(
        SkillContext(
            stage="quality_review",
            mode="api",
            testcases=(
                {
                    "case_id": "TC-001",
                    "title": "接口不可用",
                    "method": "POST",
                    "url": "/api/pay",
                    "priority": "P4",
                },
            ),
        ),
        output={},
    )

    assert set(result.metrics) == {
        "checked",
        "missing_priority",
        "invalid_priority",
        "p0_count",
        "p0_ratio",
        "p0_ratio_too_high",
        "high_risk_low_priority",
        "ui_low_risk_not_p4",
        "ui_low_risk_p4",
    }
    assert result.metrics["checked"] == 1
    assert result.metrics["high_risk_low_priority"] == 1
