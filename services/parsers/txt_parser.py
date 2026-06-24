"""
TXT / Markdown 解析器
=====================
处理纯文本和 Markdown 格式文档。
"""

import logging
import re
from pathlib import Path

from services.parsers.base import BaseParser, ParseError, ParseResult

logger = logging.getLogger(__name__)


class TxtParser(BaseParser):
    """纯文本解析器 — 支持 .txt 和 .md 格式。

    职责：读取文件原始文本内容，进行基本清洗。
    遵循 Single Responsibility 原则，只处理纯文本格式。
    """

    @property
    def format(self) -> str:
        """返回格式标识符。"""
        return "txt"

    def do_parse(self, file_path: Path) -> ParseResult:
        """解析纯文本文件。

        自动检测编码（UTF-8 / GBK），失败则用 Unicode 替换策略兜底。

        Args:
            file_path: 文件路径

        Returns:
            ParseResult — content 为完整文本内容

        Raises:
            ParseError: 文件为空或无法读取
        """
        try:
            content = self._read_with_encoding_detection(file_path)
        except Exception as exc:
            raise ParseError(
                message=f"TXT 文件读取失败: {exc}",
                file_path=file_path,
                cause=exc,
            )

        if not content or not content.strip():
            raise ParseError(
                message="文件内容为空",
                file_path=file_path,
            )

        # 文本清洗
        content = self._clean(content)

        logger.info("TXT 解析完成: %s → %d 字符", file_path.name, len(content))

        return ParseResult(
            content=content,
            filename=file_path.name,
            format=file_path.suffix.lower().lstrip("."),
        )

    def _read_with_encoding_detection(self, file_path: Path) -> str:
        """自动检测编码并读取文件。

        策略：
        1. 先用 UTF-8 读取
        2. 失败则用 GBK
        3. 再失败用 errors='replace' 兜底

        Args:
            file_path: 文件路径

        Returns:
            文件文本内容
        """
        for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    return f.read()
            except (UnicodeDecodeError, UnicodeError):
                continue

        # 兜底策略：替换无法解码的字符
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def _clean(self, text: str) -> str:
        """文本清洗。

        - 统一换行符为 \n
        - 去除连续 3 个以上的空行
        - 去除行内多余空格

        Args:
            text: 原始文本

        Returns:
            清洗后的文本
        """
        # 统一换行符
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # 去除连续 3 个以上空行，保留 2 个
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 去除行内多余空格（3个以上）
        text = re.sub(r"[ \t]{3,}", "  ", text)
        return text.strip()


class MdParser(TxtParser):
    """Markdown 解析器 — 继承 TxtParser。

    当前与 TXT 处理方式相同，预留 Markdown 语法增强处理接口。
    遵循 Open/Closed 原则：扩展不修改基类。
    """

    @property
    def format(self) -> str:
        """返回格式标识符。"""
        return "md"
