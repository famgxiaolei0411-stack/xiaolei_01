"""Tests for the API contract skill."""

from __future__ import annotations

from skills.builtin.api_contract import ApiContractSkill
from skills.core.context import SkillContext


def test_api_contract_skill_metadata() -> None:
    skill = ApiContractSkill()

    assert skill.skill_id == "api_contract"
    assert skill.metadata.name == "API Contract Check"
    assert skill.metadata.stages == ("quality_review",)
    assert skill.metadata.metadata["technique"] == "api_contract_check"


def test_api_contract_skill_ignores_functional_mode() -> None:
    skill = ApiContractSkill()

    result = skill.review_output(
        SkillContext(
            stage="quality_review",
            mode="functional",
            testcases=(
                {"case_id": "TC-001", "title": "普通功能用例"},
            ),
        ),
        output={},
    )

    assert result.issues == ()
    assert result.suggestions == ()
    assert result.metrics == {}


def test_api_contract_skill_reports_missing_method_and_url() -> None:
    skill = ApiContractSkill()

    result = skill.review_output(
        SkillContext(
            stage="quality_review",
            mode="api",
            testcases=(
                {
                    "case_id": "TC-001",
                    "title": "登录接口",
                    "expected": "返回 token",
                },
            ),
        ),
        output={},
    )

    messages = [issue.message for issue in result.issues]
    assert any("method" in message for message in messages)
    assert any("url" in message for message in messages)
    assert result.metrics["checked"] == 1
    assert result.metrics["missing_method"] == 1
    assert result.metrics["missing_url"] == 1
    assert result.metrics["contract_complete"] == 0


def test_api_contract_skill_reports_invalid_method_and_weak_expected() -> None:
    skill = ApiContractSkill()

    result = skill.review_output(
        SkillContext(
            stage="quality_review",
            mode="api",
            testcases=(
                {
                    "case_id": "TC-001",
                    "method": "FETCH",
                    "url": "api/login",
                    "expected": "成功",
                },
            ),
        ),
        output={},
    )

    messages = [issue.message for issue in result.issues]
    assert any("请求方法" in message for message in messages)
    assert any("请求路径" in message for message in messages)
    assert any("响应断言" in message for message in messages)
    assert result.metrics["invalid_method"] == 1
    assert result.metrics["weak_expected"] == 1


def test_api_contract_skill_metrics_for_complete_cases() -> None:
    skill = ApiContractSkill()

    result = skill.review_output(
        SkillContext(
            stage="quality_review",
            mode="api",
            testcases=(
                {
                    "case_id": "TC-001",
                    "method": "POST",
                    "url": "/api/login",
                    "expected": "HTTP 200，业务 code 为 0，返回 token 字段",
                },
            ),
        ),
        output={},
    )

    assert result.issues == ()
    assert result.suggestions == ()
    assert result.metrics["checked"] == 1
    assert result.metrics["contract_complete"] == 1
    assert result.metrics["contract_complete_ratio"] == 1
