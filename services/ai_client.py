"""
AI 客户端 — DeepSeek API 封装
==============================
基于 OpenAI 兼容接口调用 DeepSeek API。
提供统一的对话接口、自动重试、结构化输出解析。
"""

import json
import logging
from typing import Any

from openai import OpenAI

from config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    DEEPSEEK_MAX_TOKENS,
    DEEPSEEK_TEMPERATURE,
    DEEPSEEK_TIMEOUT,
    DEEPSEEK_MAX_RETRIES,
)

logger = logging.getLogger(__name__)


class AIClient:
    """DeepSeek API 客户端封装。

    职责：
    - 管理与 DeepSeek API 的通信
    - 自动重试失败的请求
    - 解析 AI 返回的 JSON 结构化输出
    """

    def __init__(self) -> None:
        """初始化 OpenAI 客户端，指向 DeepSeek 端点。"""
        self._client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            timeout=DEEPSEEK_TIMEOUT,
        )
        self._model = DEEPSEEK_MODEL
        self._temperature = DEEPSEEK_TEMPERATURE
        self._max_tokens = DEEPSEEK_MAX_TOKENS
        self._max_retries = DEEPSEEK_MAX_RETRIES

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """发送对话请求，返回 AI 回复文本。

        Args:
            system_prompt: 系统提示词（定义 AI 角色和行为）
            user_prompt: 用户提示词（具体的任务描述）
            temperature: 温度参数（None 则使用默认值）
            max_tokens: 最大输出 token 数（None 则使用默认值）

        Returns:
            AI 回复的原始文本内容

        Raises:
            RuntimeError: 重试全部失败后抛出
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(
                    "DeepSeek API 调用 (第 %d/%d 次)", attempt, self._max_retries
                )
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=temperature if temperature is not None else self._temperature,
                    max_tokens=max_tokens if max_tokens is not None else self._max_tokens,
                )
                content = response.choices[0].message.content or ""
                logger.info("DeepSeek API 调用成功，返回 %d 字符", len(content))
                return content

            except Exception as exc:
                last_error = exc
                logger.warning("DeepSeek API 调用失败 (第 %d 次): %s", attempt, exc)
                if attempt < self._max_retries:
                    import time
                    wait_seconds = 2 ** attempt  # 指数退避
                    logger.info("等待 %d 秒后重试...", wait_seconds)
                    time.sleep(wait_seconds)

        raise RuntimeError(
            f"DeepSeek API 调用失败，已重试 {self._max_retries} 次"
        ) from last_error

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any]:
        """发送对话请求，自动提取并解析 JSON 回复。

        AI 模型有时会在 JSON 外包裹 markdown 代码块标识符，
        本方法会自动处理这些情况。

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            temperature: 温度参数
            max_tokens: 最大输出 token 数

        Returns:
            解析后的 JSON 字典

        Raises:
            ValueError: JSON 解析失败
        """
        raw_text = self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # ── 清洗 AI 输出 ──────────────────────────
        import re

        text = raw_text.strip()

        # 策略1: 去掉 ``` 包裹（行级处理，不依赖正则跨行匹配）
        if text.startswith("```"):
            # 去掉首行的 ```json 或 ```
            first_nl = text.find("\n")
            if first_nl != -1:
                text = text[first_nl + 1:]
            else:
                text = text.lstrip("`")
        if text.endswith("```"):
            # 去掉末尾的 ```
            text = text[:-3].rstrip()
        text = text.strip()

        # 策略2: 正则去除可能的残留 ``` 标记
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()

        # 策略3: 提取最外层 JSON（从第一个 { 或 [ 到最后一个 } 或 ]）
        text = self._extract_json_bounds(text)

        # 策略4: 尝试解析（含修复）
        for _ in range(3):
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                # 尝试修复常见问题
                text = self._repair_json(text, exc)
                if text is None:
                    break

        logger.error(
            "[chat_json] 无法解析 AI 返回的 JSON，"
            "前200字符: %s", raw_text[:200]
        )
        raise ValueError(
            f"AI 返回内容无法解析为 JSON，前 200 字符: {raw_text[:200]}"
        )

    @staticmethod
    def _extract_json_bounds(text: str) -> str:
        """从文本中提取最外层 JSON 对象/数组。

        Args:
            text: 可能包含非 JSON 前缀/后缀的文本

        Returns:
            截取后的 JSON 文本
        """
        # 找第一个 { 或 [
        brace = text.find("{")
        bracket = text.find("[")
        if brace == -1 and bracket == -1:
            return text
        start = brace if bracket == -1 else (bracket if brace == -1 else min(brace, bracket))

        # 找对应的最后一个 } 或 ]
        close_char = "}" if text[start] == "{" else "]"
        end = text.rfind(close_char)
        if end > start:
            return text[start:end + 1]
        return text

    @staticmethod
    def _repair_json(text: str, exc: json.JSONDecodeError) -> str | None:
        """尝试修复常见 JSON 格式问题。

        Args:
            text: 原始 JSON 文本
            exc: JSON 解析异常

        Returns:
            修复后的文本，或 None（无法修复）
        """
        import re

        # 修复1: 去除尾随逗号（}, 或 ], 之前）
        fixed = re.sub(r',\s*([}\]])', r'\1', text)
        if fixed != text:
            try:
                json.loads(fixed)
                return fixed
            except json.JSONDecodeError:
                pass

        # 修复2: 截断到最后一个完整的对象/数组
        pos = exc.pos if hasattr(exc, 'pos') else -1
        if pos > 0:
            # 找到 pos 之前的最后一个完整结构
            # 尝试在 pos 前截断并补全
            truncated = text[:pos].rstrip()
            # 计数未闭合的括号
            open_braces = truncated.count("{") - truncated.count("}")
            open_brackets = truncated.count("[") - truncated.count("]")
            truncated += "}" * open_braces + "]" * open_brackets
            try:
                json.loads(truncated)
                return truncated
            except json.JSONDecodeError:
                pass

        return None


# ── 全局单例 ──────────────────────────────────────
_ai_client: AIClient | None = None


def get_ai_client() -> AIClient:
    """获取全局 AIClient 单例。

    Returns:
        全局唯一的 AIClient 实例
    """
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client
