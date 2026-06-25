"""
AI Test Copilot — 核心业务服务层
=================================
所有服务模块与 Web 框架完全解耦，可独立调用。

V1 (稳定): 基础文档解析 + AI 提取 + Excel 导出
V2 (新增): Pydantic 严格校验 + 重试 + RAG 知识库 + 自动化测试
"""

# ── V1 核心服务 ───────────────────────────────────
from .ai_client import AIClient, get_ai_client
from .document_parser import DocumentParser, parse_document
from .parser_service import ParserService
from .feature_extractor import FeatureExtractor
from .testpoint_generator import TestPointGenerator
from .testcase_generator import TestCaseGenerator
from .excel_exporter import ExcelExporter, export_to_excel

# ── V2 增强服务 (Pydantic 校验 + 自动重试) ─────────
from .feature_service import FeatureService, FeatureItem, FeatureResult, FeatureValidationError
from .testpoint_service import TestPointService, TestPointItem, TestPointResult, TestPointValidationError
from .testcase_service import TestCaseService, TestCaseItem, TestCaseResult, TestCaseValidationError

__all__ = [
    # V1
    "AIClient", "get_ai_client",
    "DocumentParser", "parse_document",
    "ParserService",
    "FeatureExtractor",
    "TestPointGenerator",
    "TestCaseGenerator",
    "ExcelExporter", "export_to_excel",
    # V2
    "FeatureService", "FeatureItem", "FeatureResult", "FeatureValidationError",
    "TestPointService", "TestPointItem", "TestPointResult", "TestPointValidationError",
    "TestCaseService", "TestCaseItem", "TestCaseResult", "TestCaseValidationError",
]
