"""
AI 客户端 — 多模型 API 封装
=============================
支持 DeepSeek / OpenAI / 兼容 OpenAI 格式的第三方服务。
统一对话接口、自动重试、JSON 自动修复。
"""

import json
import logging
from typing import Any

from openai import OpenAI

from config import (
    AI_PROVIDER,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    AI_MAX_TOKENS,
    AI_TEMPERATURE,
    AI_TIMEOUT,
    AI_MAX_RETRIES,
    is_configured_api_key,
)

logger = logging.getLogger(__name__)


class AIConfigurationError(RuntimeError):
    """AI 配置无效，例如 Key 缺失或仍为占位符。"""


class AIRequestError(RuntimeError):
    """AI 请求在重试后仍失败。"""


class AIResponseParseError(ValueError):
    """AI 返回内容无法解析为有效 JSON。"""


# Provider 配置表
_PROVIDER_CONFIG = {
    "deepseek": {
        "api_key": DEEPSEEK_API_KEY,
        "base_url": DEEPSEEK_BASE_URL,
        "model": DEEPSEEK_MODEL,
        "name": "DeepSeek",
        "env_name": "DEEPSEEK_API_KEY",
    },
    "openai": {
        "api_key": OPENAI_API_KEY,
        "base_url": OPENAI_BASE_URL,
        "model": OPENAI_MODEL,
        "name": "OpenAI",
        "env_name": "OPENAI_API_KEY",
    },
}


class AIClient:
    """多模型 AI 客户端封装。

    通过 AI_PROVIDER 环境变量切换模型：
    - deepseek（默认）: api.deepseek.com
    - openai: api.openai.com/v1（兼容 Azure、Ollama 等）

    职责：
    - 管理与 AI 服务的通信
    - 自动重试失败的请求
    - 解析 AI 返回的 JSON 结构化输出
    """

    def __init__(self) -> None:
        """根据 AI_PROVIDER 初始化对应的客户端。"""
        provider = AI_PROVIDER
        if provider not in _PROVIDER_CONFIG:
            raise ValueError(
                f"不支持的 AI Provider: {provider}，可选: {list(_PROVIDER_CONFIG.keys())}"
            )
        cfg = _PROVIDER_CONFIG[provider]
        api_key = (cfg["api_key"] or "").strip()
        if not is_configured_api_key(api_key):
            raise AIConfigurationError(
                f"请在 .env 中设置有效的 {cfg['env_name']}，不要保留示例值"
            )

        self._provider = cfg["name"]
        self._client = OpenAI(
            api_key=api_key,
            base_url=cfg["base_url"],
            timeout=AI_TIMEOUT,
        )
        self._model = cfg["model"]
        self._temperature = AI_TEMPERATURE
        self._max_tokens = AI_MAX_TOKENS
        self._max_retries = AI_MAX_RETRIES
        logger.info("AI 客户端初始化: provider=%s, model=%s", self._provider, self._model)

    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """发送对话请求，返回 AI 回复文本。"""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(
                    "%s API 调用 (第 %d/%d 次)", self._provider, attempt, self._max_retries
                )
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    temperature=temperature if temperature is not None else self._temperature,
                    max_tokens=max_tokens if max_tokens is not None else self._max_tokens,
                )
                content = response.choices[0].message.content or ""
                logger.info("%s API 调用成功，返回 %d 字符", self._provider, len(content))
                return content

            except Exception as exc:
                last_error = exc
                logger.warning("%s API 调用失败 (第 %d 次): %s", self._provider, attempt, exc)
                if attempt < self._max_retries:
                    import time
                    wait_seconds = 2 ** attempt
                    logger.info("等待 %d 秒后重试...", wait_seconds)
                    time.sleep(wait_seconds)

        detail = str(last_error) if last_error else "未知错误"
        raise AIRequestError(
            f"{self._provider} API 调用失败，已重试 {self._max_retries} 次: {detail}"
        ) from last_error

    def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any] | list[Any]:
        """发送对话请求，自动提取并解析 JSON 回复。"""
        raw_text = self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        import re

        text = raw_text.strip()

        if text.startswith("```"):
            first_nl = text.find("\n")
            if first_nl != -1:
                text = text[first_nl + 1:]
            else:
                text = text.lstrip("`")
        if text.endswith("```"):
            text = text[:-3].rstrip()
        text = text.strip()

        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()

        text = self._extract_json_bounds(text)

        for _ in range(3):
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                text = self._repair_json(text, exc)
                if text is None:
                    break

        logger.error(
            "[chat_json] 无法解析 AI 返回的 JSON，前200字符: %s", raw_text[:200]
        )
        raise AIResponseParseError(
            f"AI 返回内容无法解析为 JSON，前 200 字符: {raw_text[:200]}"
        )

    @staticmethod
    def _extract_json_bounds(text: str) -> str:
        """从文本中提取最外层 JSON 对象/数组。"""
        brace = text.find("{")
        bracket = text.find("[")
        if brace == -1 and bracket == -1:
            return text
        start = brace if bracket == -1 else (bracket if brace == -1 else min(brace, bracket))

        close_char = "}" if text[start] == "{" else "]"
        end = text.rfind(close_char)
        if end > start:
            return text[start:end + 1]
        return text

    @staticmethod
    def _repair_json(text: str, exc: json.JSONDecodeError) -> str | None:
        """尝试修复常见 JSON 格式问题。"""
        import re

        fixed = re.sub(r',\s*([}\]])', r'\1', text)
        if fixed != text:
            try:
                json.loads(fixed)
                return fixed
            except json.JSONDecodeError:
                pass

        pos = exc.pos if hasattr(exc, 'pos') else -1
        if pos > 0:
            truncated = text[:pos].rstrip()
            open_braces = truncated.count("{") - truncated.count("}")
            open_brackets = truncated.count("[") - truncated.count("]")
            truncated += "}" * open_braces + "]" * open_brackets
            try:
                json.loads(truncated)
                return truncated
            except json.JSONDecodeError:
                pass

        return None


_ai_client: AIClient | None = None


def get_ai_client() -> AIClient:
    """获取全局 AIClient 单例。"""
    global _ai_client
    if _ai_client is None:
        _ai_client = AIClient()
    return _ai_client
