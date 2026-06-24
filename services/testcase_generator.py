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


# ══════════════════════════════════════════════════════════
# 数据模型
# ══════════════════════════════════════════════════════════

@dataclass
class TestCase:
    """测试用例数据结构。

    Attributes:
        testpoint_description: 对应的测试点描述
        case_id: 用例编号（如 TC-LOGIN-001）
        title: 用例标题
        precondition: 前置条件
        steps: 测试步骤列表
        expected: 预期结果
        priority: 优先级
        case_type: 用例类型（正向/逆向/边界）
    """
    testpoint_description: str
    case_id: str
    title: str
    precondition: str
    steps: list[str] = field(default_factory=list)
    expected: str = ""
    priority: str = "P1"
    case_type: str = "正向"


# ══════════════════════════════════════════════════════════
# 生成器
# ══════════════════════════════════════════════════════════

class TestCaseGenerator:
    """测试用例生成器。

    流程:
    1. 将测试点列表序列化为 JSON
    2. 异步调用 AI 生成测试用例
    3. 解析并返回结构化的测试用例列表
    """

    def __init__(self, ai_client: AIClient | None = None) -> None:
        """初始化生成器。

        Args:
            ai_client: AI 客户端实例（None 则使用全局单例）
        """
        self._ai = ai_client or get_ai_client()

    def generate(self, testpoints: list[TestPoint]) -> list[TestCase]:
        """根据测试点列表生成测试用例。

        Args:
            testpoints: 测试点列表

        Returns:
            测试用例列表
        """
        if not testpoints:
            logger.warning("测试点列表为空，跳过测试用例生成")
            return []

        logger.info("开始测试用例生成，测试点数=%d", len(testpoints))

        # ── 构建测试点 JSON ────────────────────────
        testpoints_data = [
            {
                "feature_name": tp.feature_name,
                "category": tp.category,
                "description": tp.description,
                "expected_result": tp.expected_result,
                "test_data": tp.test_data,
                "priority": tp.priority,
            }
            for tp in testpoints
        ]
        testpoints_json = json.dumps(testpoints_data, ensure_ascii=False, indent=2)

        # ── 调用 AI ────────────────────────────────
        user_prompt = TESTCASE_GENERATION_USER.format(
            testpoints_json=testpoints_json
        )

        try:
            result = self._ai.chat_json(
                system_prompt=TESTCASE_GENERATION_SYSTEM,
                user_prompt=user_prompt,
                temperature=0.3,
            )
        except Exception as exc:
            logger.error("测试用例 AI 调用失败: %s", exc)
            return []

        # ── 解析结果 ────────────────────────────────
        raw_testcases = result.get("testcases", [])
        testcases: list[TestCase] = []

        for item in raw_testcases:
            try:
                testcases.append(TestCase(
                    testpoint_description=str(
                        item.get("testpoint_description", "")
                    ),
                    case_id=str(item.get("case_id", "")),
                    title=str(item.get("title", "")),
                    precondition=str(item.get("precondition", "")),
                    steps=[
                        str(s) for s in item.get("steps", []) if s
                    ],
                    expected=str(item.get("expected", "")),
                    priority=self._normalize_priority(
                        str(item.get("priority", "P1"))
                    ),
                    case_type=str(item.get("case_type", "正向")),
                ))
            except Exception as exc:
                logger.warning("跳过格式异常的测试用例: %s", exc)
                continue

        logger.info("测试用例生成完成，共 %d 个", len(testcases))
        return testcases

    @staticmethod
    def _normalize_priority(priority: str) -> str:
        """标准化优先级。"""
        priority = priority.strip().upper()
        for p in ("P0", "P1", "P2", "P3"):
            if p in priority:
                return p
        return "P1"
