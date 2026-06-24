"""
功能点提取器 — 基于 AI 从文档中提取功能点
============================================
支持长文档分块处理：每个 chunk 独立提取 → 汇总 → 去重 → 输出。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from services.ai_client import AIClient, get_ai_client
from services.document_parser import ParsedDocument
from prompts.feature_extraction import (
    FEATURE_EXTRACTION_SYSTEM,
    FEATURE_EXTRACTION_USER,
)

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════
# 数据模型
# ══════════════════════════════════════════════════════════

@dataclass
class Feature:
    """功能点数据结构。

    Attributes:
        module: 所属模块名称（如"用户管理"）
        name: 功能点名称（如"用户注册"）
        description: 详细功能描述
        priority: 优先级（P0/P1/P2/P3）
        preconditions: 前置条件列表
        business_rules: 关联业务规则列表
        source_chunk: 来自哪个文档块（溯源用）
    """
    module: str
    name: str
    description: str
    priority: str  # P0 / P1 / P2 / P3
    preconditions: list[str] = field(default_factory=list)
    business_rules: list[str] = field(default_factory=list)
    source_chunk: int = 0


# ══════════════════════════════════════════════════════════
# 提取器
# ══════════════════════════════════════════════════════════

class FeatureExtractor:
    """功能点提取器。

    流程:
    1. 对文档的每个 chunk 独立调用 AI 提取功能点
    2. 汇总所有功能点
    3. 按模块+名称去重（保留优先级最高的描述最详细的那条）
    4. 按模块和优先级排序
    """

    def __init__(self, ai_client: AIClient | None = None) -> None:
        """初始化提取器。

        Args:
            ai_client: AI 客户端实例（None 则使用全局单例）
        """
        self._ai = ai_client or get_ai_client()

    def extract(self, parsed_doc: ParsedDocument) -> list[Feature]:
        """从解析后的文档中提取所有功能点。

        Args:
            parsed_doc: 已解析的文档对象

        Returns:
            去重后的功能点列表（按模块+优先级排序）
        """
        chunk_count = len(parsed_doc.chunks)
        logger.info(
            "开始功能点提取: 文档=%s, 分块数=%d",
            parsed_doc.filename,
            chunk_count,
        )

        # ── 阶段1: 逐块提取 ───────────────────────
        all_features: list[Feature] = []

        for chunk in parsed_doc.chunks:
            logger.info(
                "提取 Chunk %d/%d (字符 %d-%d)...",
                chunk.index + 1,
                chunk_count,
                chunk.start_char,
                chunk.end_char,
            )
            features = self._extract_from_text(
                text=chunk.content,
                chunk_index=chunk.index,
            )
            logger.info("Chunk %d 提取到 %d 个功能点", chunk.index + 1, len(features))
            all_features.extend(features)

        logger.info("共提取 %d 个原始功能点（去重前）", len(all_features))

        # ── 阶段2: 去重 ───────────────────────────
        unique_features = self._deduplicate(all_features)
        logger.info("去重后保留 %d 个功能点", len(unique_features))

        # ── 阶段3: 排序 ───────────────────────────
        sorted_features = self._sort(unique_features)

        return sorted_features

    def _extract_from_text(self, text: str, chunk_index: int) -> list[Feature]:
        """对单段文本调用 AI 提取功能点。

        Args:
            text: 文本片段
            chunk_index: 块序号（用于溯源标记）

        Returns:
            提取到的功能点列表
        """
        user_prompt = FEATURE_EXTRACTION_USER.format(content=text)

        try:
            result = self._ai.chat_json(
                system_prompt=FEATURE_EXTRACTION_SYSTEM,
                user_prompt=user_prompt,
                temperature=0.2,  # 低温度确保输出稳定
            )
        except ValueError as exc:
            logger.error("Chunk %d JSON 解析失败: %s", chunk_index + 1, exc)
            raise RuntimeError(
                f"Chunk {chunk_index + 1} AI 返回无法解析: {exc}"
            ) from exc
        except Exception as exc:
            logger.error("Chunk %d AI 调用失败: %s", chunk_index + 1, exc)
            raise RuntimeError(
                f"Chunk {chunk_index + 1} AI 调用失败: {exc}"
            ) from exc

        # ── 解析 AI 返回的 JSON ───────────────────
        raw_features = result.get("features", [])
        features: list[Feature] = []

        for item in raw_features:
            try:
                features.append(Feature(
                    module=str(item.get("module", "未分类")),
                    name=str(item.get("name", "未命名")),
                    description=str(item.get("description", "")),
                    priority=self._normalize_priority(
                        str(item.get("priority", "P2"))
                    ),
                    preconditions=[
                        str(p) for p in item.get("preconditions", []) if p
                    ],
                    business_rules=[
                        str(r) for r in item.get("business_rules", []) if r
                    ],
                    source_chunk=chunk_index,
                ))
            except Exception as exc:
                logger.warning("跳过格式异常的功能点: %s", exc)
                continue

        return features

    def _deduplicate(self, features: list[Feature]) -> list[Feature]:
        """功能点去重。

        去重规则:
        - 以 (模块, 名称) 为键
        - 同名功能点保留描述最详细的那个
        - 优先级取最高值（P0 > P1 > P2 > P3）

        Args:
            features: 原始功能点列表

        Returns:
            去重后的功能点列表
        """
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

        seen: dict[tuple[str, str], Feature] = {}

        for feat in features:
            key = (feat.module.strip(), feat.name.strip())

            if key not in seen:
                seen[key] = feat
            else:
                # 保留描述更详细的
                existing = seen[key]
                if len(feat.description) > len(existing.description):
                    seen[key] = feat
                # 优先级取更高值
                if priority_order.get(feat.priority, 9) < priority_order.get(
                    existing.priority, 9
                ):
                    seen[key].priority = feat.priority
                # 合并前置条件
                for pc in feat.preconditions:
                    if pc not in seen[key].preconditions:
                        seen[key].preconditions.append(pc)
                # 合并业务规则
                for br in feat.business_rules:
                    if br not in seen[key].business_rules:
                        seen[key].business_rules.append(br)

        return list(seen.values())

    def _sort(self, features: list[Feature]) -> list[Feature]:
        """按优先级和模块排序。

        排序规则:
        1. 优先级升序（P0 在前）
        2. 同优先级按模块名称字母序
        3. 同模块按功能点名称字母序

        Args:
            features: 功能点列表

        Returns:
            排序后的功能点列表
        """
        priority_order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

        return sorted(
            features,
            key=lambda f: (
                priority_order.get(f.priority, 9),
                f.module,
                f.name,
            ),
        )

    @staticmethod
    def _normalize_priority(priority: str) -> str:
        """标准化优先级字符串。

        Args:
            priority: 原始优先级字段

        Returns:
            标准化的优先级（P0/P1/P2/P3）
        """
        priority = priority.strip().upper()
        if priority in ("P0", "P1", "P2", "P3"):
            return priority
        # 尝试从字符串中提取
        for p in ("P0", "P1", "P2", "P3"):
            if p in priority:
                return p
        return "P2"  # 默认 P2
