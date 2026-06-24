"""
解析器抽象基类 — 定义统一的解析接口（SOLID 原则）

S — Single Responsibility: 每个解析器只负责一种格式
O — Open/Closed: 新增格式无需修改现有代码
L — Liskov Substitution: 所有解析器遵循同一接口
I — Interface Segregation: 最小化接口，只定义必要方法
D — Dependency Inversion: ParserService 依赖抽象 BaseParser
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ParseResult:
    """统一的解析输出格式。

    Attributes:
        content: 完整文本内容
        filename: 原始文件名
        format: 文件格式（txt/docx/pdf/md）
        char_count: 总字符数
        metadata: 格式相关的元数据（如 PDF 页数）
    """
    content: str
    filename: str
    format: str
    char_count: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        """初始化后自动计算字符数。"""
        self.char_count = len(self.content)

    def to_dict(self) -> dict:
        """转换为字典格式，方便 JSON 序列化。

        Returns:
            {"content": "...", "filename": "...", "format": "...", ...}
        """
        return {
            "content": self.content,
            "filename": self.filename,
            "format": self.format,
            "char_count": self.char_count,
            "metadata": self.metadata,
        }


class BaseParser(ABC):
    """文档解析器抽象基类。

    所有格式解析器必须实现此接口。

    Usage:
        class NewFormatParser(BaseParser):
            @property
            def format(self) -> str:
                return "new_format"

            def do_parse(self, file_path: Path) -> ParseResult:
                ...
    """

    @property
    @abstractmethod
    def format(self) -> str:
        """返回支持的格式标识符（如 'txt', 'docx', 'pdf'）。

        Returns:
            格式字符串（不含点号）
        """
        ...

    @abstractmethod
    def do_parse(self, file_path: Path) -> ParseResult:
        """执行实际解析逻辑。

        子类必须实现此方法，包含该格式特有的解析代码。

        Args:
            file_path: 文件路径（已校验存在性）

        Returns:
            统一的 ParseResult 对象

        Raises:
            ParseError: 解析过程中发生错误
        """
        ...

    def parse(self, file_path: Path) -> ParseResult:
        """模板方法：统一的解析入口。

        包含通用校验逻辑（文件存在性、格式匹配），
        然后委托给子类的 do_parse 方法执行实际解析。

        Args:
            file_path: 文件路径

        Returns:
            ParseResult 对象

        Raises:
            FileNotFoundError: 文件不存在
            ParseError: 解析失败
        """
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        result = self.do_parse(file_path)
        return result


class ParseError(Exception):
    """解析器异常 — 所有解析相关错误的基类。

    Attributes:
        message: 错误描述
        file_path: 出错的源文件路径
        cause: 原始异常（可选）
    """

    def __init__(
        self,
        message: str,
        file_path: str | Path | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.file_path = str(file_path) if file_path else None
        self.cause = cause
