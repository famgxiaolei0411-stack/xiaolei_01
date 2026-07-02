"""Quality controls for document-driven test case generation."""

from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

from skills.builtin.api_contract import ApiContractSkill
from skills.builtin.priority_policy import PriorityPolicySkill
from skills.core.context import SkillContext
from skills.core.orchestrator import SkillOrchestrator
from skills.core.registry import SkillRegistry


MAX_TESTCASES_DEFAULT = 220
MAX_TESTCASES_API = 300
MAX_CASES_PER_FEATURE = 12
MAX_P0_RATIO = 0.18

GENERATED_SECTION_PATTERNS = [
    r"\n\s*[二三四五六七八九十]+[、.]\s*AI\s*整理需求清单[\s\S]*$",
    r"\n\s*[二三四五六七八九十]+[、.]\s*AI\s*提取测试场景[\s\S]*$",
    r"\n\s*AI\s*整理需求清单[\s\S]*$",
    r"\n\s*AI\s*提取测试场景[\s\S]*$",
    r"\n\s*测试点\s*编号\s*测试场景[\s\S]*$",
]

HIGH_RISK_PATTERN = re.compile(
    r"付款失败|扣款|充值|提现|资金损失|账务错误|数据丢失|不可恢复|越权|SQL注入|XSS|攻击|"
    r"权限绕过|认证绕过|密码泄露|token泄露|黑名单用户|风控绕过|账户封禁",
    re.IGNORECASE,
)


def sanitize_document_text(text: str) -> tuple[str, dict[str, Any]]:
    """Remove generated appendices from uploaded requirement documents."""
    cleaned = text or ""
    removed_sections: list[str] = []
    original_length = len(cleaned)

    for pattern in GENERATED_SECTION_PATTERNS:
        match = re.search(pattern, cleaned, re.IGNORECASE)
        if match:
            removed_sections.append(cleaned[match.start(): match.start() + 80].strip())
            cleaned = cleaned[:match.start()].strip()
            break

    return cleaned, {
        "original_chars": original_length,
        "cleaned_chars": len(cleaned),
        "removed_generated_sections": bool(removed_sections),
        "removed_preview": removed_sections[:2],
    }


def normalize_testcases(
    testcases: list[dict[str, Any]],
    *,
    mode: str = "functional",
    max_cases: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Deduplicate, cap, reprioritize, and renumber generated cases."""
    limit = max_cases or (MAX_TESTCASES_API if mode == "api" else MAX_TESTCASES_DEFAULT)
    before_count = len(testcases)
    seen_keys: set[str] = set()
    per_feature: Counter[str] = Counter()
    deduped: list[dict[str, Any]] = []
    duplicate_count = 0
    capped_by_feature = 0

    for case in testcases:
        feature = str(case.get("testpoint_description", "") or "未分类").strip()
        title = _norm(case.get("title", ""))
        expected = _norm(case.get("expected", ""))
        steps = _norm(" ".join(str(s) for s in case.get("steps", []) or []))
        key = f"{feature}|{title}|{expected}|{steps[:120]}"
        if key in seen_keys:
            duplicate_count += 1
            continue
        if per_feature[feature] >= MAX_CASES_PER_FEATURE:
            capped_by_feature += 1
            continue
        seen_keys.add(key)
        per_feature[feature] += 1
        deduped.append(dict(case))

    if len(deduped) > limit:
        deduped = _balanced_trim(deduped, limit)

    for case in deduped:
        case["priority"] = _normalize_priority(case)

    _cap_p0_ratio(deduped)
    _renumber_cases(deduped)

    metrics = build_quality_metrics(deduped)
    metrics.update({
        "before_count": before_count,
        "after_count": len(deduped),
        "removed_duplicates": duplicate_count,
        "removed_by_feature_cap": capped_by_feature,
        "max_cases": limit,
    })
    return deduped, metrics


def build_quality_review(testcases: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a local quality review without another LLM call."""
    metrics = build_quality_metrics(testcases)
    issues: list[dict[str, Any]] = []

    if metrics["duplicate_case_ids"] > 0:
        issues.append({"level": "error", "case_id": "-", "msg": f"存在 {metrics['duplicate_case_ids']} 个重复用例编号"})
    if metrics["duplicate_titles"] > 0:
        issues.append({"level": "warning", "case_id": "-", "msg": f"存在 {metrics['duplicate_titles']} 个重复标题"})
    if metrics["p0_ratio"] > MAX_P0_RATIO:
        issues.append({"level": "warning", "case_id": "-", "msg": f"P0 占比 {metrics['p0_ratio']:.0%} 偏高"})
    if metrics["total"] > MAX_TESTCASES_DEFAULT and metrics["mode_guess"] == "functional":
        issues.append({"level": "warning", "case_id": "-", "msg": f"功能用例数量 {metrics['total']} 偏多，建议拆批评审"})
    if metrics["empty_steps"] > 0:
        issues.append({"level": "error", "case_id": "-", "msg": f"{metrics['empty_steps']} 条用例缺少步骤"})

    score = 100
    score -= min(metrics["duplicate_case_ids"] * 3, 30)
    score -= min(metrics["duplicate_titles"] * 2, 15)
    score -= 15 if metrics["p0_ratio"] > MAX_P0_RATIO else 0
    score -= 10 if metrics["empty_steps"] else 0
    score = max(score, 40)

    review = {
        "score": score,
        "pass": score >= 70 and not any(i["level"] == "error" for i in issues),
        "summary": (
            f"共 {metrics['total']} 条用例，P0 占比 {metrics['p0_ratio']:.0%}，"
            f"重复编号 {metrics['duplicate_case_ids']} 个，重复标题 {metrics['duplicate_titles']} 个。"
        ),
        "issues": issues[:20],
        "suggestions": [
            "P0 仅保留资金、安全、数据不可恢复等高风险场景。",
            "导出前优先评审重复编号、重复标题和步骤缺失用例。",
            "超长需求建议按模块分批生成，减少一次性输出膨胀。",
        ],
        "metrics": metrics,
    }
    return _apply_quality_review_skills(review, testcases, metrics)


def build_quality_metrics(testcases: list[dict[str, Any]]) -> dict[str, Any]:
    priorities = Counter(str(tc.get("priority", "P1")) for tc in testcases)
    case_types = Counter(str(tc.get("case_type", "正向")) for tc in testcases)
    ids = Counter(str(tc.get("case_id", "")) for tc in testcases)
    titles = Counter(_norm(tc.get("title", "")) for tc in testcases)
    total = len(testcases)
    api_count = sum(1 for tc in testcases if tc.get("method") or tc.get("url"))

    return {
        "total": total,
        "priority": dict(priorities),
        "case_type": dict(case_types),
        "p0_ratio": (priorities.get("P0", 0) / total) if total else 0,
        "duplicate_case_ids": sum(1 for value in ids.values() if value > 1),
        "duplicate_titles": sum(1 for key, value in titles.items() if key and value > 1),
        "empty_steps": sum(1 for tc in testcases if not tc.get("steps")),
        "mode_guess": "api" if api_count else "functional",
    }


def dumps_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def loads_json(text: str | None, default: Any) -> Any:
    if not text:
        return default


def _build_quality_review_skill_orchestrator() -> SkillOrchestrator:
    registry = SkillRegistry()
    registry.register(ApiContractSkill())
    registry.register(PriorityPolicySkill())
    return SkillOrchestrator(registry)


def _apply_quality_review_skills(
    review: dict[str, Any],
    testcases: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Append Skill review output without changing existing score semantics."""
    original_score = review.get("score")
    original_pass = review.get("pass")
    original_summary = review.get("summary")

    try:
        orchestrator = _build_quality_review_skill_orchestrator()
        context = SkillContext(
            stage="quality_review",
            mode=str(metrics.get("mode_guess", "auto")),
            testcases=testcases,
            metadata={"source": "build_quality_review"},
        )
        result = orchestrator.review_output(context, output=review)
    except Exception:
        return review

    if result.issues:
        review.setdefault("issues", []).extend([
            {
                "level": issue.level,
                "case_id": issue.target or "-",
                "msg": issue.message,
            }
            for issue in result.issues
        ])
    if result.suggestions:
        review.setdefault("suggestions", []).extend(result.suggestions)

    if result.metrics:
        skill_reviews = review.setdefault("metrics", {}).setdefault("skill_reviews", {})
        for skill_id, skill_metrics in result.metrics.items():
            skill_reviews[skill_id] = skill_metrics

    review["score"] = original_score
    review["pass"] = original_pass
    review["summary"] = original_summary
    return review
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        return default


def _norm(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").lower())


def _normalize_priority(case: dict[str, Any]) -> str:
    text = " ".join([
        str(case.get("title", "")),
        str(case.get("expected", "")),
        " ".join(str(s) for s in case.get("steps", []) or []),
    ])
    case_type = str(case.get("case_type", "正向"))
    current = str(case.get("priority", "P1"))

    if HIGH_RISK_PATTERN.search(text):
        return "P0"
    if case_type == "边界":
        return "P2"
    if case_type == "逆向":
        return "P1"
    if current in {"P2", "P3"}:
        return current
    return "P1"


def _cap_p0_ratio(cases: list[dict[str, Any]]) -> None:
    if not cases:
        return
    max_p0 = max(1, int(len(cases) * MAX_P0_RATIO))
    p0_cases = [case for case in cases if case.get("priority") == "P0"]
    if len(p0_cases) <= max_p0:
        return
    downgraded = 0
    for case in p0_cases:
        if downgraded >= len(p0_cases) - max_p0:
            break
        case["priority"] = "P2" if case.get("case_type") == "边界" else "P1"
        downgraded += 1


def _renumber_cases(cases: list[dict[str, Any]]) -> None:
    prefixes: dict[str, int] = {}
    for index, case in enumerate(cases, 1):
        feature = str(case.get("testpoint_description", "") or "CASE")
        letters = re.findall(r"[A-Za-z]+", feature)
        if letters:
            prefix = letters[0][:8].upper()
        else:
            prefix = "CASE"
        prefixes[prefix] = prefixes.get(prefix, 0) + 1
        case["case_id"] = f"TC-{prefix}-{prefixes[prefix]:03d}"


def _balanced_trim(cases: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        buckets.setdefault(str(case.get("testpoint_description", "未分类")), []).append(case)
    result: list[dict[str, Any]] = []
    while len(result) < limit and buckets:
        for feature in list(buckets.keys()):
            if buckets[feature] and len(result) < limit:
                result.append(buckets[feature].pop(0))
            if not buckets[feature]:
                del buckets[feature]
    return result
