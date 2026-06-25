"""
FeatureService — 功能点提取服务
=================================
根据需求文本调用 DeepSeek API 提取功能点。
三层保障：API 重试 → JSON 解析 → Pydantic Schema 校验
"""

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from config import AI_MAX_RETRIES as DEEPSEEK_MAX_RETRIES
from services.ai_client import AIClient, get_ai_client
from prompts.feature_extraction_v2 import (
    FEATURE_SYSTEM_PROMPT,
    FEATURE_USER_PROMPT,
)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
# Pydantic 输出模型 — 严格校验 LLM 返回结果
# ══════════════════════════════════════════════════════════

class FeatureItem(BaseModel):
    """单个功能点。

    Attributes:
        name: 功能点名称（如"用户登录"）
        description: 清晰的功能描述
    """
    name: str = Field(..., min_length=1, max_length=200, description="功能点名称")
    description: str = Field(..., min_length=1, max_length=2000, description="功能描述")


class FeatureResult(BaseModel):
    """功能点提取结果。

    Attributes:
        features: 功能点列表
    """
    features: list[FeatureItem] = Field(
        ..., min_length=1, description="功能点列表，至少1个"
    )


# ══════════════════════════════════════════════════════════
# FeatureService
# ══════════════════════════════════════════════════════════

class FeatureValidationError(Exception):
    """LLM 返回结果校验失败异常。

    Attributes:
        message: 错误描述
        raw_response: LLM 原始返回内容（截断）
        validation_errors: Pydantic 校验错误详情
    """
    def __init__(
        self,
        message: str,
        raw_response: str = "",
        validation_errors: list[dict] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.raw_response = raw_response[:500] if raw_response else ""
        self.validation_errors = validation_errors or []


class FeatureService:
    """功能点提取服务。

    流程：
    1. 构造 Prompt（System + User）
    2. 调用 DeepSeek API（AIClient 自动处理网络层重试）
    3. 解析 JSON（清洗 markdown 包裹）
    4. Pydantic Schema 校验
    5. 校验失败 → 重试（带错误反馈）最多 3 次

    Usage:
        service = FeatureService()
        result = service.extract("用户可以通过邮箱和密码登录系统。")
        print(result.features)  # [FeatureItem(name="用户登录", description="...")]
        print(result.model_dump())  # {"features": [{"name": "...", ...}]}
    """

    # 最大语义重试次数（JSON 解析失败 / Schema 校验失败）
    MAX_VALIDATION_RETRIES: int = 3

    def __init__(self, ai_client: AIClient | None = None) -> None:
        """初始化服务。

        Args:
            ai_client: DeepSeek 客户端（None 则使用全局单例）
        """
        self._ai = ai_client or get_ai_client()

    def extract(self, content: str) -> FeatureResult:
        """从需求文本中提取功能点。

        Args:
            content: 需求文档文本（至少 10 个字符）

        Returns:
            FeatureResult — 包含功能点列表的校验结果

        Raises:
            ValueError: 输入文本过短
            FeatureValidationError: 重试耗尽后仍无法获得有效结果
            RuntimeError: DeepSeek API 调用失败
        """
        if not content or len(content.strip()) < 10:
            raise ValueError("需求文本过短（至少 10 个字符），无法提取功能点")

        content = content.strip()
        logger.info("开始功能点提取: 输入文本 %d 字符", len(content))

        last_raw: str = ""

        for attempt in range(1, self.MAX_VALIDATION_RETRIES + 1):
            logger.info("第 %d/%d 次提取尝试", attempt, self.MAX_VALIDATION_RETRIES)

            try:
                # ── 调用 AI ────────────────────────
                # AIClient.chat_json 已包含 3 次网络重试 + JSON 解析
                if attempt == 1:
                    user_prompt = FEATURE_USER_PROMPT.format(content=content)
                else:
                    # 重试时附带上次的错误信息
                    user_prompt = self._build_retry_prompt(content, last_raw)

                raw_json = self._ai.chat_json(
                    system_prompt=FEATURE_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    temperature=0.05,  # 极低温度加速输出
                )

                last_raw = json.dumps(raw_json, ensure_ascii=False)

                # ── Pydantic Schema 校验 ────────────
                result = FeatureResult.model_validate(raw_json)
                logger.info(
                    "功能点提取成功: 共 %d 个功能点", len(result.features)
                )
                return result

            except (json.JSONDecodeError, ValueError) as exc:
                # JSON 解析失败（AIClient.chat_json 已尝试修复但未成功）
                logger.warning("第 %d 次 JSON 解析失败: %s", attempt, exc)
                last_raw = str(exc)[:500]
                if attempt >= self.MAX_VALIDATION_RETRIES:
                    raise FeatureValidationError(
                        message=f"重试 {self.MAX_VALIDATION_RETRIES} 次后 LLM 仍未返回有效 JSON",
                        raw_response=last_raw,
                    ) from exc

            except ValidationError as exc:
                # Pydantic Schema 校验失败
                errors = exc.errors()
                logger.warning(
                    "第 %d 次 Schema 校验失败: %s", attempt, errors
                )
                if attempt >= self.MAX_VALIDATION_RETRIES:
                    raise FeatureValidationError(
                        message=f"重试 {self.MAX_VALIDATION_RETRIES} 次后 LLM 输出仍不符合 Schema",
                        raw_response=last_raw,
                        validation_errors=errors,
                    ) from exc

            except RuntimeError:
                # AIClient 网络层重试耗尽
                raise

            except Exception as exc:
                logger.error("第 %d 次未预期错误: %s", attempt, exc)
                if attempt >= self.MAX_VALIDATION_RETRIES:
                    raise FeatureValidationError(
                        message=f"重试 {self.MAX_VALIDATION_RETRIES} 次后仍失败: {exc}",
                        raw_response=last_raw,
                    ) from exc

        # 不应到达这里
        raise FeatureValidationError(
            message=f"重试 {self.MAX_VALIDATION_RETRIES} 次后仍未获得有效结果",
            raw_response=last_raw,
        )

    def _build_retry_prompt(self, content: str, last_raw: str) -> str:
        """构建重试 Prompt — 告知 LLM 上次的错误。

        通过反馈上次输出的问题，引导 LLM 自我修正。

        Args:
            content: 原始需求文本
            last_raw: 上次 LLM 的原始输出（或错误信息）

        Returns:
            包含错误反馈的 User Prompt
        """
        return f"""## 需求文档内容
{content}

## 上次输出的问题
你的上次输出格式不正确，解析失败。请严格按以下规则修正：

1. 只输出纯 JSON，不要有任何解释文字
2. JSON 格式必须为：{{"features": [{{"name": "功能点名称", "description": "功能描述"}}]}}
3. features 不能为空数组
4. 每个 feature 必须包含 name 和 description 两个字段

上次的错误信息：{last_raw[:300]}

现在请重新提取功能点，只输出正确的 JSON："""

    def extract_to_dict(self, content: str) -> dict[str, Any]:
        """快捷方法：提取并返回字典格式。

        Args:
            content: 需求文档文本

        Returns:
            {"features": [{"name": "...", "description": "..."}, ...]}
        """
        result = self.extract(content)
        return result.model_dump()
