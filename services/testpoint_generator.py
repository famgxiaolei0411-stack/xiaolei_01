"""
测试点生成器 — 基于 AI 为功能点生成测试点
============================================
"""

import json
import logging
from dataclasses import dataclass, field

from services.ai_client import AIClient, get_ai_client
from services.feature_extractor import Feature
from prompts.testpoint_generation import (
    TESTPOINT_GENERATION_SYSTEM,
    TESTPOINT_GENERATION_USER,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# 数据模型
# ══════════════════════════════════════════════════════════

@dataclass
class TestPoint:
    """测试点数据结构。

    Attributes:
        feature_name: 对应的功能点名称
        category: 测试类型（功能测试/业务规则/异常场景/数据测试/性能测试/安全测试/兼容性测试）
        description: 测试点具体描述
        expected_result: 预期结果
        test_data: 建议测试数据（可选）
        priority: 优先级
    """
    feature_name: str
    category: str
    description: str
    expected_result: str
    test_data: str = ""
    priority: str = "P1"


# ══════════════════════════════════════════════════════════
# 生成器
# ══════════════════════════════════════════════════════════

class TestPointGenerator:
    """测试点生成器。

    流程:
    1. 将功能点列表序列化为 JSON
    2. 异步调用 AI 生成测试点
    3. 解析并返回结构化测试点列表
    """

    def __init__(self, ai_client: AIClient | None = None) -> None:
        """初始化生成器。

        Args:
            ai_client: AI 客户端实例（None 则使用全局单例）
        """
        self._ai = ai_client or get_ai_client()

    def generate(self, features: list[Feature]) -> list[TestPoint]:
        """根据功能点列表生成测试点。

        Args:
            features: 功能点列表

        Returns:
            测试点列表
        """
        if not features:
            logger.warning("功能点列表为空，跳过测试点生成")
            return []

        logger.info("开始测试点生成，功能点数=%d", len(features))

        # ── 构建功能点 JSON ────────────────────────
        features_data = [
            {
                "module": f.module,
                "name": f.name,
                "description": f.description,
                "priority": f.priority,
                "preconditions": f.preconditions,
                "business_rules": f.business_rules,
            }
            for f in features
        ]
        features_json = json.dumps(features_data, ensure_ascii=False, indent=2)

        # ── 调用 AI ────────────────────────────────
        user_prompt = TESTPOINT_GENERATION_USER.format(
            features_json=features_json
        )

        try:
            result = self._ai.chat_json(
                system_prompt=TESTPOINT_GENERATION_SYSTEM,
                user_prompt=user_prompt,
                temperature=0.3,
            )
        except Exception as exc:
            logger.error("测试点 AI 调用失败: %s", exc)
            return []

        # ── 解析结果 ────────────────────────────────
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
                    priority=self._normalize_priority(
                        str(item.get("priority", "P1"))
                    ),
                ))
            except Exception as exc:
                logger.warning("跳过格式异常的测试点: %s", exc)
                continue

        logger.info("测试点生成完成，共 %d 个", len(testpoints))
        return testpoints

    @staticmethod
    def _normalize_priority(priority: str) -> str:
        """标准化优先级。"""
        priority = priority.strip().upper()
        for p in ("P0", "P1", "P2", "P3"):
            if p in priority:
                return p
        return "P1"
