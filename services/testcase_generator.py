"""
测试用例生成器 — 基于 AI 为测试点生成可执行的测试用例
========================================================
"""

import json
import logging
from dataclasses import dataclass, field

from services.ai_client import AIClient, get_ai_client
from services.testpoint_generator import TestPoint
from prompts.testcase_generation import (
    TESTCASE_GENERATION_SYSTEM,
    TESTCASE_GENERATION_USER,
)

logger = logging.getLogger(__name__)


@dataclass
class TestCase:
    """测试用例数据结构。"""

    testpoint_description: str
    case_id: str
    title: str
    precondition: str
    steps: list[str] = field(default_factory=list)
    expected: str = ""
    priority: str = "P1"
    case_type: str = "正向"


class TestCaseGenerator:
    """测试用例生成器。"""

    def __init__(self, ai_client: AIClient | None = None) -> None:
        self._ai = ai_client or get_ai_client()

    def generate(self, testpoints: list[TestPoint]) -> list[TestCase]:
        if not testpoints:
            logger.warning("测试点列表为空，跳过测试用例生成")
            return []

        logger.info("开始测试用例生成，测试点数=%d", len(testpoints))
        testpoints_data = [
            {
                "feature_name": item.feature_name,
                "category": item.category,
                "description": item.description,
                "expected_result": item.expected_result,
                "test_data": item.test_data,
                "priority": item.priority,
            }
            for item in testpoints
        ]
        testpoints_json = json.dumps(testpoints_data, ensure_ascii=False, indent=2)
        user_prompt = TESTCASE_GENERATION_USER.format(testpoints_json=testpoints_json)

        try:
            result = self._ai.chat_json(
                system_prompt=TESTCASE_GENERATION_SYSTEM,
                user_prompt=user_prompt,
                temperature=0.3,
            )
        except Exception as exc:
            logger.error("测试用例 AI 调用失败: %s", exc)
            raise RuntimeError(f"测试用例生成失败: {exc}") from exc

        if not isinstance(result, dict):
            raise ValueError(f"测试用例生成返回格式错误: {type(result).__name__}")

        raw_testcases = result.get("testcases", [])
        testcases: list[TestCase] = []

        for item in raw_testcases:
            try:
                testcases.append(TestCase(
                    testpoint_description=str(item.get("testpoint_description", "")),
                    case_id=str(item.get("case_id", "")),
                    title=str(item.get("title", "")),
                    precondition=str(item.get("precondition", "")),
                    steps=[str(step) for step in item.get("steps", []) if step],
                    expected=str(item.get("expected", "")),
                    priority=self._normalize_priority(str(item.get("priority", "P1"))),
                    case_type=str(item.get("case_type", "正向")),
                ))
            except Exception as exc:
                logger.warning("跳过格式异常的测试用例: %s", exc)

        if not testcases:
            raise ValueError("测试用例生成结果为空")

        logger.info("测试用例生成完成，共 %d 个", len(testcases))
        return testcases

    @staticmethod
    def _normalize_priority(priority: str) -> str:
        priority = priority.strip().upper()
        for value in ("P0", "P1", "P2", "P3"):
            if value in priority:
                return value
        return "P1"
