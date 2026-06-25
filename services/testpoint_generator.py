"""
测试点生成器 — 基于 AI 为功能点生成测试点
============================================
"""

import json
import logging
from dataclasses import dataclass

from services.ai_client import AIClient, get_ai_client
from services.feature_extractor import Feature
from prompts.testpoint_generation import (
    TESTPOINT_GENERATION_SYSTEM,
    TESTPOINT_GENERATION_USER,
)

logger = logging.getLogger(__name__)


@dataclass
class TestPoint:
    """测试点数据结构。"""

    feature_name: str
    category: str
    description: str
    expected_result: str
    test_data: str = ""
    priority: str = "P1"


class TestPointGenerator:
    """测试点生成器。"""

    def __init__(self, ai_client: AIClient | None = None) -> None:
        self._ai = ai_client or get_ai_client()

    def generate(self, features: list[Feature]) -> list[TestPoint]:
        if not features:
            logger.warning("功能点列表为空，跳过测试点生成")
            return []

        logger.info("开始测试点生成，功能点数=%d", len(features))
        features_data = [
            {
                "module": feature.module,
                "name": feature.name,
                "description": feature.description,
                "priority": feature.priority,
                "preconditions": feature.preconditions,
                "business_rules": feature.business_rules,
            }
            for feature in features
        ]
        features_json = json.dumps(features_data, ensure_ascii=False, indent=2)
        user_prompt = TESTPOINT_GENERATION_USER.format(features_json=features_json)

        try:
            result = self._ai.chat_json(
                system_prompt=TESTPOINT_GENERATION_SYSTEM,
                user_prompt=user_prompt,
                temperature=0.3,
            )
        except Exception as exc:
            logger.error("测试点 AI 调用失败: %s", exc)
            raise RuntimeError(f"测试点生成失败: {exc}") from exc

        if not isinstance(result, dict):
            raise ValueError(f"测试点生成返回格式错误: {type(result).__name__}")

        raw_testpoints = result.get("testpoints", [])
        testpoints: list[TestPoint] = []

        for item in raw_testpoints:
            try:
                testpoints.append(TestPoint(
                    feature_name=str(item.get("feature_name", "")),
                    category=str(item.get("category", "功能测试")),
                    description=str(item.get("description", "")),
                    expected_result=str(item.get("expected_result", "")),
                    test_data=str(item.get("test_data", "")),
                    priority=self._normalize_priority(str(item.get("priority", "P1"))),
                ))
            except Exception as exc:
                logger.warning("跳过格式异常的测试点: %s", exc)

        if not testpoints:
            raise ValueError("测试点生成结果为空")

        logger.info("测试点生成完成，共 %d 个", len(testpoints))
        return testpoints

    @staticmethod
    def _normalize_priority(priority: str) -> str:
        priority = priority.strip().upper()
        for value in ("P0", "P1", "P2", "P3"):
            if value in priority:
                return value
        return "P1"
