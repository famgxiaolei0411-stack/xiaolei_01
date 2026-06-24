"""
解析器注册表 — 统一管理所有文档格式解析器
===========================================
新增加格式只需在此注册，无需修改 ParserService。
"""

from services.parsers.base import BaseParser, ParseResult
from services.parsers.txt_parser import TxtParser
from services.parsers.docx_parser import DocxParser
from services.parsers.pdf_parser import PdfParser

__all__ = [
    "BaseParser",
    "ParseResult",
    "TxtParser",
    "DocxParser",
    "PdfParser",
]
