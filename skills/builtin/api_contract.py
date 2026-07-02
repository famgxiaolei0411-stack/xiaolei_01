"""API contract review skill."""

from __future__ import annotations

from typing import Any, Mapping

from skills.core.base import BaseSkill, SkillMetadata
from skills.core.context import SkillContext
from skills.core.result import SkillIssue, SkillResult


VALID_HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
WEAK_EXPECTED_VALUES = {"", "成功", "失败", "正常", "通过", "ok", "OK"}


class ApiContractSkill(BaseSkill):
    """Review API testcase contract completeness with local rules only."""

    metadata = SkillMetadata(
        skill_id="api_contract",
        name="API Contract Check",
        description="Check API testcase method, url, and response assertions.",
        stages=("quality_review",),
        priority=40,
        metadata={
            "technique": "api_contract_check",
            "category": "quality_review",
        },
    )

    def review_output(
        self,
        context: SkillContext,
        output: Any,
    ) -> SkillResult:
        """Review API testcase contract fields without mutating input."""

        if context.mode == "functional":
            return SkillResult.empty(self.skill_id)

        testcases = list(context.testcases)
        if context.mode == "auto" and not self._looks_like_api_cases(testcases):
            return SkillResult.empty(self.skill_id)

        checked = len(testcases)
        missing_method = 0
        missing_url = 0
        invalid_method = 0
        weak_expected = 0
        complete = 0
        issues: list[SkillIssue] = []

        for index, testcase in enumerate(testcases, 1):
            case_id = str(
                testcase.get("case_id")
                or testcase.get("id")
                or f"#{index}"
            )
            method = str(testcase.get("method", "") or "").strip().upper()
            url = str(testcase.get("url", "") or "").strip()
            expected = str(
                testcase.get("expected")
                or testcase.get("expected_result")
                or ""
            ).strip()

            case_complete = True

            if not method:
                missing_method += 1
                case_complete = False
                issues.append(self._issue(case_id, "接口用例缺少请求方法 method"))
            elif method not in VALID_HTTP_METHODS:
                invalid_method += 1
                case_complete = False
                issues.append(self._issue(case_id, f"请求方法不常见或不合法: {method}"))

            if not url:
                missing_url += 1
                case_complete = False
                issues.append(self._issue(case_id, "接口用例缺少请求路径 url"))
            elif not self._looks_like_url(url):
                case_complete = False
                issues.append(self._issue(case_id, f"请求路径格式不清晰: {url}"))

            if expected in WEAK_EXPECTED_VALUES or len(expected) < 5:
                weak_expected += 1
                case_complete = False
                issues.append(self._issue(
                    case_id,
                    "接口响应断言过于笼统，建议包含状态码、业务 code 或关键字段",
                    level="info",
                ))

            if case_complete:
                complete += 1

        metrics = {
            "checked": checked,
            "missing_method": missing_method,
            "missing_url": missing_url,
            "invalid_method": invalid_method,
            "weak_expected": weak_expected,
            "contract_complete": complete,
            "contract_complete_ratio": (complete / checked) if checked else 0,
        }

        suggestions = ()
        if issues:
            suggestions = (
                "接口用例建议补充 method、url、请求参数和响应断言。",
                "响应断言建议包含状态码、业务 code、关键字段或错误信息。",
            )

        return SkillResult(
            skill_id=self.skill_id,
            issues=tuple(issues),
            suggestions=suggestions,
            metrics=metrics,
            metadata={"mode": context.mode},
        )

    @staticmethod
    def _looks_like_api_cases(testcases: list[Mapping[str, Any]]) -> bool:
        return any(case.get("method") or case.get("url") for case in testcases)

    @staticmethod
    def _looks_like_url(url: str) -> bool:
        return (
            url.startswith("/")
            or url.startswith("http://")
            or url.startswith("https://")
        )

    def _issue(
        self,
        case_id: str,
        message: str,
        *,
        level: str = "warning",
    ) -> SkillIssue:
        return SkillIssue(
            skill_id=self.skill_id,
            level=level,
            target=case_id,
            message=message,
        )
