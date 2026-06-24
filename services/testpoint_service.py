"""
TestPointService — 测试点生成服务
====================================
输入功能点名称+描述，输出四维度全覆盖测试点 JSON。

保障机制：
- 网络层：AIClient 指数退避重试 3 次
- 解析层：自动清洗 LLM 输出的 markdown 包裹
- 语义层：Pydantic Schema 校验 + 四维度强制覆盖 + 最多 3 次重试
"""

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from services.ai_client import AIClient, get_ai_client
from prompts.testpoint_generation_v2 import (
    TESTPOINT_SYSTEM_PROMPT,
    TESTPOINT_USER_PROMPT,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# Pydantic 输出模型 — 严格校验 LLM 返回结果
# ══════════════════════════════════════════════════════════

# 四个强制维度
VALID_CATEGORIES = Literal["功能测试", "异常测试", "安全测试", "边界值测试"]
REQUIRED_CATEGORIES: set[str] = {"功能测试", "异常测试", "安全测试", "边界值测试"}


class TestPointItem(BaseModel):
    """单个测试点。

    每个字段都设置了严格约束，确保 LLM 输出可用。
    """
    id: str = Field(
        ...,
        min_length=3,
        max_length=20,
        description="测试点编号（如 TP-001）",
    )
    category: str = Field(
        ...,
        description="测试类型：功能测试 / 异常测试 / 安全测试 / 边界值测试",
    )
    description: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="测试点具体描述（含具体输入/动作，不可笼统）",
    )
    expected_result: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="明确的预期结果",
    )
    test_data: str = Field(
        default="",
        max_length=500,
        description="建议使用的测试数据",
    )
    priority: Literal["P0", "P1", "P2", "P3"] = Field(
        default="P1",
        description="优先级",
    )

    @model_validator(mode="after")
    def validate_category(self) -> "TestPointItem":
        """校验 category 必须为四个合法值之一。"""
        if self.category not in REQUIRED_CATEGORIES:
            raise ValueError(
                f"无效的 category: '{self.category}'，"
                f"必须为: {', '.join(sorted(REQUIRED_CATEGORIES))}"
            )
        return self


class TestPointResult(BaseModel):
    """测试点生成结果。

    包含双重校验：
    1. 基础 Schema 校验（字段类型、长度）
    2. 业务规则校验（四维度覆盖、数量要求）
    """
    feature_name: str = Field(..., min_length=1, max_length=200)
    test_points: list[TestPointItem] = Field(..., min_length=1)

    @model_validator(mode="after")
    def validate_coverage(self) -> "TestPointResult":
        """业务规则校验：四维度全覆盖 + 数量门槛。

        规则：
        - 每个维度至少 1 个测试点
        - 总计至少 6 个测试点
        - ID 不可重复
        """
        if len(self.test_points) < 6:
            raise ValueError(
                f"测试点数量不足：{len(self.test_points)} 个（最少需要 6 个）"
            )

        # ── 四维度覆盖检查 ───────────────────────
        covered: set[str] = set()
        seen_ids: set[str] = set()

        for tp in self.test_points:
            covered.add(tp.category)
            if tp.id in seen_ids:
                raise ValueError(f"测试点 ID 重复: {tp.id}")
            seen_ids.add(tp.id)

        missing = REQUIRED_CATEGORIES - covered
        if missing:
            raise ValueError(
                f"以下维度未覆盖: {sorted(missing)}，已覆盖: {sorted(covered)}"
            )

        return self


# ══════════════════════════════════════════════════════════
# 异常定义
# ══════════════════════════════════════════════════════════

class TestPointValidationError(Exception):
    """LLM 生成结果校验失败。

    Attributes:
        message: 错误描述
        raw_response: LLM 原始返回（截断至 500 字符）
        category_gap: 缺失的维度（用于向用户展示）
    """
    def __init__(
        self,
        message: str,
        raw_response: str = "",
        category_gap: set[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.raw_response = raw_response[:500] if raw_response else ""
        self.category_gap = category_gap or set()


# ══════════════════════════════════════════════════════════
# TestPointService
# ══════════════════════════════════════════════════════════

class TestPointService:
    """测试点生成服务。

    流程：
    1. 输入校验（功能点名称不能为空）
    2. 构造四维度覆盖 Prompt
    3. 调用 DeepSeek API（AIClient 自动网络重试）
    4. Pydantic 双重校验（字段 + 四维度覆盖）
    5. 校验失败 → 带错误反馈重试（最多 3 次）

    Usage:
        service = TestPointService()
        result = service.generate("用户登录", "用户通过用户名密码验证身份后进入系统")
        print(result.model_dump())
        # {
        #   "feature_name": "用户登录",
        #   "test_points": [
        #     {"id": "TP-001", "category": "功能测试", ...},
        #     {"id": "TP-003", "category": "异常测试", ...},
        #     {"id": "TP-005", "category": "安全测试", ...},
        #     {"id": "TP-007", "category": "边界值测试", ...},
        #     ...
        #   ]
        # }
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
        feature_description: str = "",
    ) -> TestPointResult:
        """为功能点生成四维度全覆盖的测试点。

        Args:
            feature_name: 功能点名称（如"用户登录"）
            feature_description: 功能点描述（可选，提供更详细的上下文）

        Returns:
            TestPointResult — 包含 feature_name + test_points 的校验结果

        Raises:
            ValueError: 功能点名称为空
            TestPointValidationError: 重试耗尽后仍无法获得有效结果
        """
        # ── 输入校验 ──────────────────────────────
        if not feature_name or not feature_name.strip():
            raise ValueError("功能点名称不能为空")

        feature_name = feature_name.strip()
        feature_description = (feature_description or "").strip() or "暂无详细描述"

        logger.info(
            "开始生成测试点: 功能点=%s, 描述长度=%d",
            feature_name,
            len(feature_description),
        )

        last_raw: str = ""

        for attempt in range(1, self.MAX_VALIDATION_RETRIES + 1):
            logger.info("第 %d/%d 次生成尝试", attempt, self.MAX_VALIDATION_RETRIES)

            try:
                # ── 构造 Prompt ────────────────────
                if attempt == 1:
                    user_prompt = TESTPOINT_USER_PROMPT.format(
                        feature_name=feature_name,
                        feature_description=feature_description,
                    )
                else:
                    user_prompt = self._build_retry_prompt(
                        feature_name, feature_description, last_raw
                    )

                # ── 调用 AI ────────────────────────
                raw_json = self._ai.chat_json(
                    system_prompt=TESTPOINT_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.3,
                )
                last_raw = json.dumps(raw_json, ensure_ascii=False)

                # ── Pydantic 双重校验 ──────────────
                result = TestPointResult.model_validate(raw_json)

                # ── 校验 feature_name 匹配 ──────────
                if result.feature_name != feature_name:
                    logger.warning(
                        "LLM 返回的 feature_name 不匹配: '%s' vs '%s'，修正为输入值",
                        result.feature_name,
                        feature_name,
                    )
                    result.feature_name = feature_name

                logger.info(
                    "测试点生成成功: %d 个测试点, 覆盖维度: %s",
                    len(result.test_points),
                    sorted({tp.category for tp in result.test_points}),
                )
                return result

            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("第 %d 次 JSON 解析失败: %s", attempt, exc)
                last_raw = str(exc)[:500]
                if attempt >= self.MAX_VALIDATION_RETRIES:
                    raise TestPointValidationError(
                        message=f"重试 {self.MAX_VALIDATION_RETRIES} 次后 LLM 仍未返回有效 JSON",
                        raw_response=last_raw,
                    ) from exc

            except ValidationError as exc:
                errors = exc.errors()
                logger.warning("第 %d 次 Schema 校验失败: %s", attempt, errors)

                # ── 分析缺失维度 ────────────────────
                category_gap = self._analyze_category_gap(errors)

                if attempt >= self.MAX_VALIDATION_RETRIES:
                    raise TestPointValidationError(
                        message=f"重试 {self.MAX_VALIDATION_RETRIES} 次后仍不符合要求",
                        raw_response=last_raw,
                        category_gap=category_gap,
                    ) from exc

            except RuntimeError:
                raise

            except Exception as exc:
                logger.error("第 %d 次未预期错误: %s", attempt, exc)
                if attempt >= self.MAX_VALIDATION_RETRIES:
                    raise TestPointValidationError(
                        message=f"重试 {self.MAX_VALIDATION_RETRIES} 次后仍失败: {exc}",
                        raw_response=last_raw,
                    ) from exc

        raise TestPointValidationError(
            message=f"重试 {self.MAX_VALIDATION_RETRIES} 次后仍未获得有效结果",
            raw_response=last_raw,
        )

    def _build_retry_prompt(
        self,
        feature_name: str,
        feature_description: str,
        last_error: str,
    ) -> str:
        """构建带错误反馈的重试 Prompt。

        Args:
            feature_name: 功能点名称
            feature_description: 功能点描述
            last_error: 上次的输出/错误信息

        Returns:
            包含错误反馈的 User Prompt
        """
        return f"""## 功能点信息
功能点名称：{feature_name}
功能描述：{feature_description}

## 上次输出的问题
你的上次输出不符合要求，请严格按以下规则修正：

1. 只输出纯 JSON，不要有任何解释文字
2. 四维度必须全部覆盖：功能测试、异常测试、安全测试、边界值测试
3. 每个维度至少 2 个测试点
4. 总测试点数量至少 6 个
5. category 字段必须是四个值之一
6. priority 必须是 P0/P1/P2/P3 之一

上次的错误信息：{last_error[:300]}

现在请重新生成测试点，严格遵守格式要求，只输出正确的 JSON："""

    def _analyze_category_gap(
        self, errors: list[dict]
    ) -> set[str]:
        """从校验错误中分析缺少哪些维度。

        Args:
            errors: Pydantic ValidationError.errors() 返回的错误列表

        Returns:
            缺失的维度集合
        """
        gap: set[str] = REQUIRED_CATEGORIES.copy()
        for err in errors:
            msg = str(err.get("msg", ""))
            # 从"以下维度未覆盖"类错误中提取
            if "未覆盖" in msg:
                covered_part = msg.split("已覆盖:")[-1] if "已覆盖:" in msg else ""
                if covered_part:
                    try:
                        import ast
                        covered = set(ast.literal_eval(covered_part.strip()))
                        gap = REQUIRED_CATEGORIES - covered
                    except Exception:
                        pass
        return gap

    def generate_to_dict(self, feature_name: str, description: str = "") -> dict[str, Any]:
        """快捷方法：生成并返回字典格式。

        Args:
            feature_name: 功能点名称
            description: 功能点描述

        Returns:
            {"feature_name": "...", "test_points": [{...}, ...]}
        """
        result = self.generate(feature_name, description)
        return result.model_dump()
