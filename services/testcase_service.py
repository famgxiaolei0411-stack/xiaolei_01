"""
TestCaseService — 测试用例生成服务
=====================================
输入测试点 → 输出符合 IEEE 829 标准的可执行测试用例。

保障机制：
- Pydantic 严格校验（字段完整性 + 内容质量 + ID 唯一性）
- 校验失败自动重试（最多 3 次，带错误反馈）
- AIClient 网络层自动重试（指数退避）
"""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError, model_validator

from services.ai_client import AIClient, get_ai_client
from prompts.testcase_generation_v2 import (
    TESTCASE_API_SYSTEM_PROMPT,
    TESTCASE_API_USER_PROMPT,
    TESTCASE_FUNC_SYSTEM_PROMPT,
    TESTCASE_FUNC_USER_PROMPT,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# Pydantic 输出模型 — 严格校验每条测试用例
# ══════════════════════════════════════════════════════════

class TestCaseItem(BaseModel):
    """单条测试用例。

    校验规则覆盖完整性 + 内容质量两个维度。
    """
    id: str = Field(
        ...,
        min_length=5,
        max_length=30,
        description="用例编号（如 TC-LOGIN-001）",
    )
    title: str = Field(
        ...,
        min_length=5,
        max_length=200,
        description="用例标题（被测对象 - 场景 - 预期行为）",
    )
    precondition: str = Field(
        default="无",
        max_length=500,
        description="前置条件",
    )
    steps: list[str] = Field(
        default_factory=list,
        min_length=0,
        max_length=20,
        description="操作步骤数组（接口用例可为空，用 method/url/body 替代）",
    )
    test_data: str = Field(
        default="",
        max_length=500,
        description="建议测试数据",
    )
    expected_result: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="预期结果（具体、可客观验证）",
    )
    method: str = Field(default="", max_length=10, description="请求方法 GET/POST/PUT/DELETE")
    url: str = Field(default="", max_length=500, description="请求路径")
    headers: str = Field(default="", max_length=500, description="请求头 JSON")
    body: str = Field(default="", max_length=2000, description="请求体 JSON")

    @model_validator(mode="after")
    def validate_steps_format(self) -> "TestCaseItem":
        """校验步骤格式：每步必须以数字序号开头。

        正面示例: "1. 打开登录页面"
        反面示例: "打开登录页面"（无序号）
        """
        for i, step in enumerate(self.steps, 1):
            step = step.strip()
            if not (step.startswith(f"{i}.") or step.startswith(f"{i}．")):
                raise ValueError(
                    f"步骤 {i} 格式错误: '{step[:30]}' 应以 '{i}.' 开头"
                )
        return self


class TestCaseResult(BaseModel):
    """测试用例生成结果 — 用例列表。

    校验：
    - 列表不能为空
    - ID 不可重复
    - 每条用例通过 TestCaseItem 校验
    """
    testcases: list[TestCaseItem] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_ids_unique(self) -> "TestCaseResult":
        """校验用例 ID 唯一性。"""
        seen: set[str] = set()
        for tc in self.testcases:
            if tc.id in seen:
                raise ValueError(f"用例 ID 重复: {tc.id}")
            seen.add(tc.id)
        return self


# ══════════════════════════════════════════════════════════
# 异常定义
# ══════════════════════════════════════════════════════════

class TestCaseValidationError(Exception):
    """测试用例校验失败。

    Attributes:
        message: 错误描述
        raw_response: LLM 原始输出（截断）
    """
    def __init__(
        self,
        message: str,
        raw_response: str = "",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.raw_response = raw_response[:500] if raw_response else ""


# ══════════════════════════════════════════════════════════
# TestCaseService
# ══════════════════════════════════════════════════════════

class TestCaseService:
    """测试用例生成服务。

    流程：
    1. 将测试点列表序列化为 JSON 输入
    2. 调用 DeepSeek API 生成测试用例
    3. Pydantic 双重校验（字段 + ID 唯一性）
    4. 校验失败 → 带错误反馈重试（最多 3 次）

    Usage:
        service = TestCaseService()
        cases = service.generate("用户登录", [
            {"category": "功能测试", "description": "正常用户名密码登录"},
            {"category": "异常测试", "description": "用户名为空"},
        ])
        for tc in cases:
            print(tc.model_dump())
    """

    MAX_VALIDATION_RETRIES: int = 3

    def __init__(self, ai_client: AIClient | None = None) -> None:
        """初始化服务。

        Args:
            ai_client: DeepSeek 客户端（None 则使用全局单例）
        """
        self._ai = ai_client or get_ai_client()

    def generate(
        self,
        feature_name: str,
        test_points: list[dict[str, str]],
        mode: str = "api",
    ) -> list[TestCaseItem]:
        """根据测试点生成测试用例。

        Args:
            feature_name: 功能点名称
            test_points: 测试点列表
            mode: "api"(接口测试) 或 "functional"(功能测试)

        Returns:
            TestCaseItem 列表
        """
        if not feature_name or not feature_name.strip():
            raise ValueError("功能点名称不能为空")
        if not test_points:
            raise ValueError("测试点列表不能为空")

        feature_name = feature_name.strip()
        testpoints_json = json.dumps(test_points, ensure_ascii=False, indent=2)
        is_api = (mode == "api")

        logger.info(
            "开始生成测试用例: mode=%s, 功能=%s, 测试点数=%d",
            mode, feature_name, len(test_points),
        )

        last_raw: str = ""

        for attempt in range(1, self.MAX_VALIDATION_RETRIES + 1):
            logger.info("第 %d/%d 次生成尝试", attempt, self.MAX_VALIDATION_RETRIES)

            try:
                # ── 构造 Prompt ────────────────────
                if attempt == 1:
                    user_prompt = (TESTCASE_API_USER_PROMPT if is_api else TESTCASE_FUNC_USER_PROMPT).format(
                        feature_name=feature_name,
                        testpoints_json=testpoints_json,
                    )
                else:
                    user_prompt = self._build_retry_prompt(
                        feature_name, testpoints_json, last_raw
                    )

                raw_json = self._ai.chat_json(
                    system_prompt=TESTCASE_API_SYSTEM_PROMPT if is_api else TESTCASE_FUNC_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.1,  # 低温度加速输出
                )
                last_raw = json.dumps(raw_json, ensure_ascii=False)

                # ── 标准化输入格式 ──────────────────
                # LLM 可能返回 {"testcases": [...]} 或直接返回 [...]
                if isinstance(raw_json, dict) and "testcases" in raw_json:
                    items = raw_json["testcases"]
                elif isinstance(raw_json, list):
                    items = raw_json
                else:
                    raise ValueError(
                        f"LLM 返回格式异常，期望数组或含 testcases 字段的对象，"
                        f"实际类型: {type(raw_json).__name__}"
                    )

                # ── Pydantic 校验 ──────────────────
                result = TestCaseResult.model_validate({"testcases": items})

                logger.info(
                    "测试用例生成成功: %d 条用例", len(result.testcases)
                )
                return result.testcases

            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("第 %d 次 JSON 解析失败: %s", attempt, exc)
                last_raw = str(exc)[:500]
                if attempt >= self.MAX_VALIDATION_RETRIES:
                    raise TestCaseValidationError(
                        message=f"重试 {self.MAX_VALIDATION_RETRIES} 次后仍无法获得有效结果",
                        raw_response=last_raw,
                    ) from exc

            except ValidationError as exc:
                errors = exc.errors()
                logger.warning(
                    "第 %d 次 Schema 校验失败: %d 个错误", attempt, len(errors)
                )
                # 只记录前 3 个错误到日志
                for err in errors[:3]:
                    logger.warning("  - %s: %s", err.get("loc", []), err.get("msg"))

                if attempt >= self.MAX_VALIDATION_RETRIES:
                    raise TestCaseValidationError(
                        message=f"重试 {self.MAX_VALIDATION_RETRIES} 次后输出仍不符合 Schema",
                        raw_response=last_raw,
                    ) from exc

            except RuntimeError:
                raise

            except Exception as exc:
                logger.error("第 %d 次未预期错误: %s", attempt, exc)
                if attempt >= self.MAX_VALIDATION_RETRIES:
                    raise TestCaseValidationError(
                        message=f"重试 {self.MAX_VALIDATION_RETRIES} 次后仍失败: {exc}",
                        raw_response=last_raw,
                    ) from exc

        raise TestCaseValidationError(
            message=f"重试 {self.MAX_VALIDATION_RETRIES} 次后仍未获得有效结果",
            raw_response=last_raw,
        )

    def _build_retry_prompt(
        self,
        feature_name: str,
        testpoints_json: str,
        last_error: str,
    ) -> str:
        """构建带错误反馈的重试 Prompt。

        Args:
            feature_name: 功能点名称
            testpoints_json: 测试点 JSON 字符串
            last_error: 上次校验失败的错误信息

        Returns:
            包含错误反馈的 User Prompt
        """
        return f"""## 功能点名称
{feature_name}

## 测试点列表
{testpoints_json}

## 上次输出的问题
你的上次输出不符合规范要求，校验失败。请严格修正：

1. 每条用例必须包含 id/title/precondition/steps/expected_result 五个字段
2. steps 为字符串数组，每步以"序号. "开头，原子化、不可合并
3. expected_result 必须具体、可验证，不可笼统
4. 用例 ID 不可重复
5. 只输出纯 JSON 数组，不要任何解释文字

上次错误信息：{last_error[:400]}

现在请重新生成，严格遵守规范，只输出正确的 JSON 数组："""

    def generate_to_dict(
        self,
        feature_name: str,
        test_points: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """快捷方法：生成并返回字典列表。

        Args:
            feature_name: 功能点名称
            test_points: 测试点列表

        Returns:
            [{"id": "TC001", "title": "...", "precondition": "...",
              "steps": [...], "expected_result": "..."}, ...]
        """
        cases = self.generate(feature_name, test_points)
        return [tc.model_dump() for tc in cases]

    # ══════════════════════════════════════════════════════
    # 自评审
    # ══════════════════════════════════════════════════════

    def review(self, feature_name: str, cases: list) -> dict[str, Any]:
        """对已生成的用例进行 AI 自评审。

        Returns:
            {
                "score": 85,           # 总分 0-100
                "pass": true,          # 是否通过 (>60)
                "summary": "整体质量良好...",
                "issues": [            # 发现的问题
                    {"level": "warning", "case_id": "TC-001", "msg": "步骤不够原子化"},
                ],
                "suggestions": [       # 改进建议
                    "建议为边界值测试补充更多测试数据",
                ]
            }
        """
        if not cases:
            return {"score": 0, "pass": False, "summary": "无用例可评审", "issues": [], "suggestions": []}

        # 本地快速检查
        issues = self._quick_check(cases)
        total = len(cases)
        issue_count = len(issues)
        base_score = max(100 - issue_count * 3, 40)

        # AI 深度评审（抽样最多 15 条避免 token 过大）
        sample = cases[:15]
        ai_feedback = self._ai_review(feature_name, sample, total)

        # 合并评分
        final_score = int((base_score + ai_feedback.get("score", 70)) / 2)
        all_issues = issues + ai_feedback.get("issues", [])
        suggestions = ai_feedback.get("suggestions", [])

        return {
            "score": min(final_score, 100),
            "pass": final_score >= 60,
            "summary": ai_feedback.get("summary", f"共 {total} 条用例，发现 {len(all_issues)} 个问题"),
            "issues": all_issues[:10],
            "suggestions": suggestions[:5],
        }

    def _quick_check(self, cases: list) -> list[dict]:
        """快速本地检查（无需 AI）。兼容 dict 和 TestCaseItem 两种格式。"""
        issues = []

        for i, tc in enumerate(cases):
            # 兼容两种 key 命名：API 传 dict (case_id/expected)，Pydantic 用 (id/expected_result)
            cid = (getattr(tc, "id", None) or tc.get("id") or
                   tc.get("case_id") or f"#{i+1}")
            title = getattr(tc, "title", "") or tc.get("title", "") or ""
            steps = getattr(tc, "steps", []) or tc.get("steps", []) or []
            expected = (getattr(tc, "expected_result", None) or tc.get("expected_result") or
                       tc.get("expected") or "")

            # 标题长度检查
            if len(title) < 8:
                issues.append({"level": "warning", "case_id": str(cid), "msg": f"标题过短 ({len(title)}字): {title[:30]}"})
            # 步骤数量检查
            if len(steps) < 2:
                issues.append({"level": "error", "case_id": str(cid), "msg": "步骤少于 2 步"})
            # 步骤格式检查
            for s in steps:
                if s is None:
                    continue
                s_str = str(s).strip()
                if not s_str:
                    continue
                if not (s_str[0].isdigit() and (". " in s_str[:5] or "．" in s_str[:5])):
                    issues.append({"level": "info", "case_id": str(cid), "msg": f"步骤缺少编号: {s_str[:30]}"})
                    break
            # 预期结果长度
            if len(expected) < 5:
                issues.append({"level": "warning", "case_id": str(cid), "msg": f"预期结果过短 ({len(expected)}字)"})

        return issues

    def _ai_review(self, feature_name: str, sample: list, total: int) -> dict[str, Any]:
        """AI 深度评审（抽样）。"""
        # 序列化为简化格式（兼容两种 key 命名）
        cases_json = []
        for tc in sample:
            if isinstance(tc, dict):
                cid = tc.get("case_id") or tc.get("id", "")
                title = tc.get("title", "")
                steps = tc.get("steps", [])
                expected = tc.get("expected") or tc.get("expected_result", "")
            else:
                cid = tc.id
                title = tc.title
                steps = tc.steps
                expected = tc.expected_result
            cases_json.append({
                "id": cid,
                "title": title,
                "steps": (steps or [])[:5],
                "expected": expected or "",
            })

        review_prompt = f"""你是一位资深测试架构师。请评审以下 {len(sample)} 条测试用例（共 {total} 条，抽样评审）。

功能点: {feature_name}

用例列表:
{json.dumps(cases_json, ensure_ascii=False, indent=2)}

请从以下维度评审，只输出 JSON:
1. 步骤原子化（每步只做一件事）
2. 预期结果可验证（具体、可测量）
3. 覆盖率（正向/逆向/边界是否合理）
4. 测试数据是否充分

输出格式:
{{
  "score": 85,
  "summary": "整体质量良好，步骤清晰...",
  "issues": [{{"level": "error|warning|info", "case_id": "TC-001", "msg": "描述"}}],
  "suggestions": ["建议1", "建议2"]
}}"""

        try:
            result = self._ai.chat_json(
                system_prompt="你是资深测试架构师，只输出 JSON，不输出任何解释。",
                user_prompt=review_prompt,
                temperature=0.1,
            )
            return result
        except Exception as exc:
            logger.warning("AI 评审调用失败，使用本地检查结果: %s", exc)
            return {"score": 0, "summary": "AI 评审暂不可用（已使用本地检查）", "issues": [], "suggestions": []}
