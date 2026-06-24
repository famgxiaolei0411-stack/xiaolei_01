"""
ParserService — 统一的文档解析服务入口
==========================================
封装所有格式解析器，对外提供统一接口。

遵循 SOLID 原则：
- S: 只负责协调和路由，不参与具体格式解析
- O: 新增格式只需注册到 _parsers 字典，无需修改本类
- D: 依赖 BaseParser 抽象而非具体实现
"""

import logging
from pathlib import Path
from typing import Type

from services.parsers.base import BaseParser, ParseError, ParseResult
from services.parsers.txt_parser import TxtParser, MdParser
from services.parsers.docx_parser import DocxParser
from services.parsers.pdf_parser import PdfParser

logger = logging.getLogger(__name__)


class ParserService:
    """文档解析服务 — 统一入口。

    自动根据文件扩展名路由到对应的解析器。

    Usage:
        service = ParserService()
        result = service.parse("需求文档.docx")
        print(result.to_dict())  # {"content": "...", "filename": "...", ...}
        print(result.content)    # 完整文本
    """

    # ── 解析器注册表 ─────────────────────────────
    # 新增格式只需在此添加一行映射即可
    _parsers: dict[str, BaseParser] = {
        "txt": TxtParser(),
        "md": MdParser(),
        "docx": DocxParser(),
        "pdf": PdfParser(),
    }

    @classmethod
    def register(cls, ext: str, parser: BaseParser) -> None:
        """注册新的解析器（Open/Closed 原则）。

        允许在不修改 ParserService 代码的情况下扩展新格式。

        Args:
            ext: 文件扩展名（如 'html'）
            parser: 对应的解析器实例

        Example:
            ParserService.register("html", HtmlParser())
        """
        ext = ext.lower().lstrip(".")
        cls._parsers[ext] = parser
        logger.info("注册解析器: .%s → %s", ext, type(parser).__name__)

    @classmethod
    def supported_formats(cls) -> list[str]:
        """获取已支持的格式列表。

        Returns:
            格式扩展名列表（如 ['txt', 'md', 'docx', 'pdf']）
        """
        return list(cls._parsers.keys())

    def parse(self, file_path: str | Path) -> ParseResult:
        """解析文档，自动识别格式并输出统一结果。

        流程：
        1. 校验文件存在性
        2. 根据扩展名选择解析器
        3. 委托给对应解析器执行解析
        4. 返回统一的 ParseResult

        Args:
            file_path: 文档文件路径（支持 .txt / .md / .docx / .pdf）

        Returns:
            ParseResult — 包含 content 完整文本和元信息

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 不支持的文件格式
            ParseError: 解析过程中发生错误

        Example:
            >>> service = ParserService()
            >>> result = service.parse("需求说明书.docx")
            >>> result.to_dict()
            {
                "content": "完整的文档文本...",
                "filename": "需求说明书.docx",
                "format": "docx",
                "char_count": 12345,
                "metadata": {}
            }
        """
        file_path = Path(file_path)

        # ── 1. 校验文件存在性 ────────────────────
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # ── 2. 根据扩展名路由 ────────────────────
        ext = file_path.suffix.lower().lstrip(".")
        if not ext:
            raise ValueError(f"文件无扩展名，无法识别格式: {file_path.name}")

        parser = self._parsers.get(ext)
        if parser is None:
            raise ValueError(
                f"不支持的文件格式: .{ext}，"
                f"当前支持: {', '.join(self._parsers.keys())}"
            )

        logger.info("路由到 %s 解析: %s", type(parser).__name__, file_path.name)

        # ── 3. 委托解析 ──────────────────────────
        try:
            result = parser.parse(file_path)
        except ParseError:
            # ParseError 直接上抛，已经是格式化好的
            raise
        except Exception as exc:
            # 其他未知异常包装为 ParseError
            raise ParseError(
                message=f"解析过程发生未知错误: {exc}",
                file_path=file_path,
                cause=exc,
            )

        return result

    def parse_to_dict(self, file_path: str | Path) -> dict:
        """快捷方法：解析并直接返回字典格式。

        Args:
            file_path: 文档文件路径

        Returns:
            {"content": "完整文本", "filename": "...", "format": "...",
             "char_count": N, "metadata": {...}}
        """
        result = self.parse(file_path)
        return result.to_dict()
