"""
PDF 解析器
===========
解析 PDF 格式文档，逐页提取文本。
"""

import logging
from pathlib import Path

from services.parsers.base import BaseParser, ParseError, ParseResult

logger = logging.getLogger(__name__)


class PdfParser(BaseParser):
    """PDF 文档解析器 — 只负责 .pdf 格式。

    使用 pypdf 逐页提取文本。
    遵循 Single Responsibility 原则。
    """

    @property
    def format(self) -> str:
        """返回格式标识符。"""
        return "pdf"

    def do_parse(self, file_path: Path) -> ParseResult:
        """解析 PDF 文件。

        逐页提取文本，跳过空白页。

        Args:
            file_path: 文件路径

        Returns:
            ParseResult — content 为所有页文本的拼接，
            metadata 中包含 page_count（总页数）

        Raises:
            ParseError: 文件加密、损坏或无法解析
        """
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ParseError(
                message="缺少 pypdf 依赖，请执行: pip install pypdf",
                file_path=file_path,
                cause=exc,
            )

        try:
            reader = PdfReader(str(file_path))
        except Exception as exc:
            raise ParseError(
                message=f"PDF 文件打开失败，文件可能已加密或损坏: {exc}",
                file_path=file_path,
                cause=exc,
            )

        total_pages = len(reader.pages)
        if total_pages == 0:
            raise ParseError(
                message="PDF 文件为空（0 页）",
                file_path=file_path,
            )

        pages: list[str] = []
        empty_pages: int = 0

        for i, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text()
                if text and text.strip():
                    pages.append(text.strip())
                else:
                    empty_pages += 1
            except Exception as exc:
                logger.warning("PDF 第 %d 页提取失败: %s", i, exc)
                empty_pages += 1

        if not pages:
            raise ParseError(
                message=f"PDF 共 {total_pages} 页，但未能提取到文本（"
                        f"可能为扫描件或图片型 PDF）",
                file_path=file_path,
            )

        content = "\n\n".join(pages)

        logger.info(
            "PDF 解析完成: %s → %d 页(有效 %d 页), %d 字符",
            file_path.name,
            total_pages,
            total_pages - empty_pages,
            len(content),
        )

        return ParseResult(
            content=content,
            filename=file_path.name,
            format="pdf",
            metadata={
                "page_count": total_pages,
                "pages_with_text": total_pages - empty_pages,
            },
        )

