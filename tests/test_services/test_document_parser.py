"""
文档解析器单元测试
====================
测试各格式文档的解析和分块功能。
"""

from pathlib import Path

from services.document_parser import DocumentParser, ParsedDocument


class TestDocumentParser:
    """DocumentParser 单元测试。"""

    def test_parse_txt_file(self, sample_txt_file: Path) -> None:
        """测试解析 TXT 文件。"""
        parser = DocumentParser()
        result = parser.parse(sample_txt_file)

        assert isinstance(result, ParsedDocument)
        assert result.filename == "test_requirements.txt"
        assert result.file_type == ".txt"
        assert len(result.full_text) > 0
        assert "用户注册" in result.full_text
        assert "用户登录" in result.full_text
        assert "密码修改" in result.full_text

    def test_chunking(self, sample_txt_file: Path) -> None:
        """测试长文本分块功能。"""
        # 使用较小的 chunk_size 强制分块
        parser = DocumentParser(chunk_size=100, chunk_overlap=20)
        result = parser.parse(sample_txt_file)

        assert len(result.chunks) > 1, "文本应该被分成多个块"
        # 每个块的内容不应为空
        for chunk in result.chunks:
            assert len(chunk.content) > 0
        # 块索引应连续
        indices = [c.index for c in result.chunks]
        assert indices == list(range(len(indices)))

    def test_parse_unsupported_format(self) -> None:
        """测试不支持的格式抛出异常。"""
        parser = DocumentParser()
        try:
            parser.parse("test.xyz")
            assert False, "应该抛出异常"
        except ValueError as exc:
            assert "不支持" in str(exc)

    def test_parse_nonexistent_file(self) -> None:
        """测试不存在的文件抛出异常。"""
        parser = DocumentParser()
        try:
            parser.parse("nonexistent_file.txt")
            assert False, "应该抛出异常"
        except FileNotFoundError:
            pass

    def test_chunk_overlap(self, sample_txt_file: Path) -> None:
        """测试 chunk 重叠策略。"""
        parser = DocumentParser(chunk_size=200, chunk_overlap=50)
        result = parser.parse(sample_txt_file)

        if len(result.chunks) > 1:
            # 验证相邻块之间有内容重叠
            for i in range(len(result.chunks) - 1):
                current_end = result.chunks[i].end_char
                next_start = result.chunks[i + 1].start_char
                # 后一块的起始应在前一块的结束之前（有重叠）
                assert next_start < current_end, (
                    f"Chunk {i} 和 Chunk {i+1} 之间没有重叠"
                )
