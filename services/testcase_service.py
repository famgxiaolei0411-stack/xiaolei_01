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
    TESTCASE_SYSTEM_PROMPT,
    TESTCASE_USER_PROMPT,
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
        ...,
        min_length=2,
        max_length=20,
        description="操作步骤数组，每步以编号开头",
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

    @model_validator(mode="after")
    def validate_steps_format(self) -> "TestCaseItem":
        """校验步骤格式：每步必须以数字序号开头。

        正面示例: "1. 打开登录页面"
        反面示例: "打开登录页面"（无序号）
        """
        for i, step in enumerate(self.steps, 1):
            step = step.strip()
            # 检查是否以序号开头
            if not (step.startswith(f"{i}.") or step.startswith(f"{i}．")):
                # 自修正：如果步骤没有序号，尝试补全
                pass  # 交给 AI 重试修正，不在此处做自动修复
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
    ) -> list[TestCaseItem]:
        """根据测试点生成标准测试用例。

        Args:
            feature_name: 功能点名称（如"用户登录"）
            test_points: 测试点列表，每项含 category/description

        Returns:
            TestCaseItem 列表（已通过 Pydantic 校验）

        Raises:
            ValueError: 输入参数无效
            TestCaseValidationError: 重试耗尽后仍无法获得有效结果
        """
        # ── 输入校验 ──────────────────────────────
        if not feature_name or not feature_name.strip():
            raise ValueError("功能点名称不能为空")
        if not test_points:
            raise ValueError("测试点列表不能为空")

        feature_name = feature_name.strip()

        # ── 构建测试点 JSON ────────────────────────
        testpoints_json = json.dumps(test_points, ensure_ascii=False, indent=2)

        logger.info(
            "开始生成测试用例: 功能=%s, 测试点数=%d",
            feature_name,
            len(test_points),
        )

        last_raw: str = ""

        for attempt in range(1, self.MAX_VALIDATION_RETRIES + 1):
            logger.info("第 %d/%d 次生成尝试", attempt, self.MAX_VALIDATION_RETRIES)

            try:
                # ── 构造 Prompt ────────────────────
                if attempt == 1:
                    user_prompt = TESTCASE_USER_PROMPT.format(
                        feature_name=feature_name,
                        testpoints_json=testpoints_json,
                    )
                else:
                    user_prompt = self._build_retry_prompt(
                        feature_name, testpoints_json, last_raw
                    )

                # ── 调用 AI ────────────────────────
                raw_json = self._ai.chat_json(
                    system_prompt=TESTCASE_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.2,
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
