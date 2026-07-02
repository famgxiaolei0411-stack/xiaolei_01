"""Tests for local quality review skill integration."""

from __future__ import annotations

from services import quality_review
from services.quality_review import build_quality_review


def test_quality_review_appends_api_contract_metrics() -> None:
    review = build_quality_review([
        {
            "case_id": "TC-001",
            "title": "登录接口 - 正常登录",
            "steps": ["1. 请求登录接口", "2. 校验响应"],
            "expected": "返回 token",
            "priority": "P1",
            "method": "POST",
            "url": "/api/login",
        }
    ])

    api_metrics = review["metrics"]["skill_reviews"]["api_contract"]
    assert api_metrics["checked"] == 1
    assert api_metrics["contract_complete"] == 1
    assert api_metrics["contract_complete_ratio"] == 1
    assert "priority_policy" in review["metrics"]["skill_reviews"]


def test_quality_review_appends_api_contract_issues() -> None:
    review = build_quality_review([
        {
            "case_id": "TC-001",
            "title": "登录接口 - 缺请求方法",
            "steps": ["1. 请求登录接口", "2. 校验响应"],
            "expected": "成功",
            "priority": "P1",
            "method": "",
            "url": "/api/login",
        },
        {
            "case_id": "TC-002",
            "title": "登录接口 - 缺请求路径",
            "steps": ["1. 请求登录接口", "2. 校验响应"],
            "expected": "成功",
            "priority": "P1",
            "method": "POST",
            "url": "",
        },
    ])

    messages = [issue["msg"] for issue in review["issues"]]
    assert any("method" in message for message in messages)
    assert any("url" in message for message in messages)
    assert any("响应断言" in message for message in messages)
    api_metrics = review["metrics"]["skill_reviews"]["api_contract"]
    assert api_metrics["missing_method"] == 1
    assert api_metrics["missing_url"] == 1


def test_quality_review_does_not_change_score_pass_or_summary() -> None:
    testcases = [
        {
            "case_id": "TC-001",
            "title": "登录接口 - 缺请求方法",
            "steps": ["1. 请求登录接口", "2. 校验响应"],
            "expected": "成功",
            "priority": "P1",
            "method": "",
            "url": "/api/login",
        }
    ]

    original_build = quality_review._build_quality_review_skill_orchestrator
    try:
        quality_review._build_quality_review_skill_orchestrator = lambda: _NoSkillOrchestrator()
        base_review = build_quality_review(testcases)
    finally:
        quality_review._build_quality_review_skill_orchestrator = original_build

    review = build_quality_review(testcases)

    assert review["score"] == base_review["score"]
    assert review["pass"] == base_review["pass"]
    assert review["summary"] == base_review["summary"]


def test_quality_review_functional_mode_has_priority_policy_but_no_api_contract_review() -> None:
    review = build_quality_review([
        {
            "case_id": "TC-001",
            "title": "登录页面 - 正常登录",
            "steps": ["1. 输入账号密码", "2. 点击登录"],
            "expected": "进入首页",
            "priority": "P1",
            "case_type": "正向",
        }
    ])

    assert "priority_policy" in review["metrics"]["skill_reviews"]
    assert "api_contract" not in review["metrics"]["skill_reviews"]
    assert not any("接口用例" in issue["msg"] for issue in review["issues"])


def test_quality_review_appends_priority_policy_metrics_and_issues() -> None:
    review = build_quality_review([
        {
            "case_id": "TC-001",
            "title": "登录安全检查",
            "steps": ["输入异常 token"],
            "expected": "拒绝访问",
            "priority": "P4",
        },
        {
            "case_id": "TC-002",
            "title": "按钮文案展示",
            "steps": ["打开页面"],
            "expected": "文案清晰",
            "priority": "P1",
        },
        {
            "case_id": "TC-003",
            "title": "普通检查",
            "steps": ["打开页面"],
            "expected": "展示正常",
            "priority": "PX",
        },
    ])

    metrics = review["metrics"]["skill_reviews"]["priority_policy"]
    assert metrics["checked"] == 3
    assert metrics["invalid_priority"] == 1
    assert metrics["high_risk_low_priority"] == 1
    assert metrics["ui_low_risk_not_p4"] == 1
    messages = [issue["msg"] for issue in review["issues"]]
    assert any("P0/P1" in message for message in messages)
    assert any("P4" in message for message in messages)


def test_quality_review_priority_policy_applies_to_api_mode() -> None:
    review = build_quality_review([
        {
            "case_id": "TC-001",
            "title": "支付接口不可用",
            "steps": ["请求支付接口"],
            "expected": "返回错误码",
            "priority": "P4",
            "method": "POST",
            "url": "/api/pay",
        }
    ])

    metrics = review["metrics"]["skill_reviews"]["priority_policy"]
    assert metrics["checked"] == 1
    assert metrics["high_risk_low_priority"] == 1


def test_quality_review_skill_failure_returns_original_review() -> None:
    testcases = [
        {
            "case_id": "TC-001",
            "title": "登录接口 - 正常登录",
            "steps": ["1. 请求登录接口", "2. 校验响应"],
            "expected": "返回 token",
            "priority": "P1",
            "method": "POST",
            "url": "/api/login",
        }
    ]

    original_build = quality_review._build_quality_review_skill_orchestrator
    try:
        quality_review._build_quality_review_skill_orchestrator = lambda: _FailingOrchestrator()
        review = build_quality_review(testcases)
    finally:
        quality_review._build_quality_review_skill_orchestrator = original_build

    assert "skill_reviews" not in review["metrics"]


class _NoSkillOrchestrator:
    def review_output(self, context, output):
        from skills.core.result import SkillResult

        return SkillResult(skill_id="orchestrator")


class _FailingOrchestrator:
    def review_output(self, context, output):
        raise RuntimeError("skill failed")
