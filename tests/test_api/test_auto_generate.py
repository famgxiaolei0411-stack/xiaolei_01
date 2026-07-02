from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from backend.api import export as export_api
import services.testcase_service as testcase_service_module


@pytest.mark.asyncio
async def test_auto_generate_rolls_back_when_testcase_generation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    project = SimpleNamespace(
        name="示例项目",
        doc_content="用户可以登录系统，并支持密码错误提示。",
        doc_filename="req.txt",
    )
    monkeypatch.setattr(export_api, "get_project", AsyncMock(return_value=project))
    monkeypatch.setattr(export_api, "save_features", AsyncMock())
    monkeypatch.setattr(export_api, "save_testpoints", AsyncMock())
    monkeypatch.setattr(export_api, "save_testcases", AsyncMock())
    monkeypatch.setattr(export_api, "update_project_status", AsyncMock())

    monkeypatch.setattr("services.ai_client.get_ai_client", lambda: object())
    monkeypatch.setattr(
        "services.document_classifier.classify_document",
        lambda content: SimpleNamespace(doc_type="requirement", mode="functional", confidence=0.95),
    )

    class DummyParser:
        def _chunk_text(self, content: str):
            return [SimpleNamespace(content=content)]

    monkeypatch.setattr("services.document_parser.DocumentParser", DummyParser)
    monkeypatch.setattr(
        "services.document_parser.ParsedDocument",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )

    class DummyFeatureService:
        def __init__(self, ai_client) -> None:
            self.ai_client = ai_client

        def extract(self, content: str):
            return SimpleNamespace(
                features=[SimpleNamespace(name="用户登录", description="用户输入账号密码登录")]
            )

    class DummyTestPointService:
        def __init__(self, ai_client=None) -> None:
            self.ai_client = ai_client

        def generate(self, feature_name: str, feature_description: str = ""):
            return SimpleNamespace(
                feature_name=feature_name,
                test_points=[
                    SimpleNamespace(
                        category="功能测试",
                        description="输入正确账号密码登录",
                        expected_result="登录成功",
                        test_data="账号/密码",
                        priority="P1",
                    )
                ],
            )

    class FailingTestCaseService:
        def __init__(self, ai_client=None) -> None:
            self.ai_client = ai_client

        def generate(self, feature_name: str, test_points: list[dict], mode: str = "functional"):
            raise testcase_service_module.TestCaseValidationError("LLM 输出仍不符合 Schema")

    monkeypatch.setattr("services.feature_service.FeatureService", DummyFeatureService)
    monkeypatch.setattr("services.testpoint_service.TestPointService", DummyTestPointService)
    monkeypatch.setattr("services.testcase_service.TestCaseService", FailingTestCaseService)

    with pytest.raises(HTTPException) as exc_info:
        await export_api.auto_generate_all(project_id=1, db=db)

    assert "测试用例生成失败" in str(exc_info.value.detail)
    export_api.save_features.assert_awaited_once()
    export_api.save_testpoints.assert_awaited_once()
    export_api.save_testcases.assert_not_awaited()
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_auto_generate_commits_once_after_full_success(
    monkeypatch: pytest.MonkeyPatch,
    temp_dir: Path,
) -> None:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    project = SimpleNamespace(
        name="示例项目",
        doc_content="用户可以登录系统，并支持密码错误提示。",
        doc_filename="req.txt",
    )
    monkeypatch.setattr(export_api, "get_project", AsyncMock(return_value=project))
    monkeypatch.setattr(export_api, "save_features", AsyncMock())
    monkeypatch.setattr(export_api, "save_testpoints", AsyncMock())
    monkeypatch.setattr(export_api, "save_testcases", AsyncMock())
    monkeypatch.setattr(export_api, "update_project_status", AsyncMock())

    monkeypatch.setattr("services.ai_client.get_ai_client", lambda: object())
    monkeypatch.setattr(
        "services.document_classifier.classify_document",
        lambda content: SimpleNamespace(doc_type="requirement", mode="functional", confidence=0.95),
    )

    class DummyParser:
        def _chunk_text(self, content: str):
            return [SimpleNamespace(content=content)]

    monkeypatch.setattr("services.document_parser.DocumentParser", DummyParser)
    monkeypatch.setattr(
        "services.document_parser.ParsedDocument",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )

    class DummyFeatureService:
        def __init__(self, ai_client) -> None:
            self.ai_client = ai_client

        def extract(self, content: str):
            return SimpleNamespace(
                features=[SimpleNamespace(name="用户登录", description="用户输入账号密码登录")]
            )

    class DummyTestPointService:
        def __init__(self, ai_client=None) -> None:
            self.ai_client = ai_client

        def generate(self, feature_name: str, feature_description: str = ""):
            return SimpleNamespace(
                feature_name=feature_name,
                test_points=[
                    SimpleNamespace(
                        category="功能测试",
                        description="输入正确账号密码登录",
                        expected_result="登录成功",
                        test_data="账号/密码",
                        priority="P1",
                    ),
                    SimpleNamespace(
                        category="异常测试",
                        description="密码错误",
                        expected_result="提示错误",
                        test_data="错误密码",
                        priority="P1",
                    ),
                    SimpleNamespace(
                        category="安全测试",
                        description="SQL 注入",
                        expected_result="请求被拦截",
                        test_data="' or 1=1 --",
                        priority="P1",
                    ),
                    SimpleNamespace(
                        category="边界值测试",
                        description="超长密码",
                        expected_result="提示长度不合法",
                        test_data="超长密码",
                        priority="P1",
                    ),
                ],
            )

    class DummyTestCaseService:
        def __init__(self, ai_client=None) -> None:
            self.ai_client = ai_client

        def generate(self, feature_name: str, test_points: list[dict], mode: str = "functional"):
            return [
                SimpleNamespace(
                    id="TC-001",
                    title="用户登录成功",
                    precondition="已打开登录页",
                    steps=["1. 输入账号密码", "2. 点击登录按钮"],
                    expected_result="登录成功",
                )
            ]

    class DummyExporter:
        def export(self, data):
            file_path = temp_dir / "demo.xlsx"
            file_path.write_bytes(b"xlsx")
            return file_path

    monkeypatch.setattr("services.feature_service.FeatureService", DummyFeatureService)
    monkeypatch.setattr("services.testpoint_service.TestPointService", DummyTestPointService)
    monkeypatch.setattr("services.testcase_service.TestCaseService", DummyTestCaseService)
    monkeypatch.setattr(export_api, "ExcelExporter", DummyExporter)

    result = await export_api.auto_generate_all(project_id=1, db=db)

    assert result.ok is True
    assert result.data["features"] == 1
    assert result.data["testpoints"] == 4
    assert result.data["testcases"] == 1
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_auto_generate_rolls_back_when_export_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    project = SimpleNamespace(
        name="示例项目",
        doc_content="用户可以登录系统，并支持密码错误提示。",
        doc_filename="req.txt",
    )
    monkeypatch.setattr(export_api, "get_project", AsyncMock(return_value=project))
    monkeypatch.setattr(export_api, "save_features", AsyncMock())
    monkeypatch.setattr(export_api, "save_testpoints", AsyncMock())
    monkeypatch.setattr(export_api, "save_testcases", AsyncMock())
    monkeypatch.setattr(export_api, "save_quality_review", AsyncMock())
    monkeypatch.setattr(export_api, "update_project_status", AsyncMock())

    monkeypatch.setattr("services.ai_client.get_ai_client", lambda: object())
    monkeypatch.setattr(
        "services.document_classifier.classify_document",
        lambda content: SimpleNamespace(doc_type="requirement", mode="functional", confidence=0.95),
    )

    class DummyParser:
        def _chunk_text(self, content: str):
            return [SimpleNamespace(content=content)]

    monkeypatch.setattr("services.document_parser.DocumentParser", DummyParser)
    monkeypatch.setattr(
        "services.document_parser.ParsedDocument",
        lambda **kwargs: SimpleNamespace(**kwargs),
    )

    class DummyFeatureService:
        def __init__(self, ai_client) -> None:
            self.ai_client = ai_client

        def extract(self, content: str):
            return SimpleNamespace(
                features=[SimpleNamespace(name="用户登录", description="用户输入账号密码登录")]
            )

    class DummyTestPointService:
        def __init__(self, ai_client=None) -> None:
            self.ai_client = ai_client

        def generate(self, feature_name: str, feature_description: str = ""):
            return SimpleNamespace(
                feature_name=feature_name,
                test_points=[
                    SimpleNamespace(category="功能测试", description="正常登录", expected_result="登录成功", test_data="ok", priority="P1"),
                    SimpleNamespace(category="异常测试", description="密码错误", expected_result="提示错误", test_data="bad", priority="P1"),
                    SimpleNamespace(category="安全测试", description="SQL 注入", expected_result="拦截", test_data="' or 1=1", priority="P0"),
                    SimpleNamespace(category="边界值测试", description="超长密码", expected_result="提示长度", test_data="long", priority="P2"),
                ],
            )

    class DummyTestCaseService:
        def __init__(self, ai_client=None) -> None:
            self.ai_client = ai_client

        def generate(self, feature_name: str, test_points: list[dict], mode: str = "functional"):
            return [
                SimpleNamespace(
                    id="TC-001",
                    title="用户登录成功",
                    precondition="已打开登录页",
                    steps=["1. 输入账号密码", "2. 点击登录按钮"],
                    expected_result="登录成功",
                )
            ]

    class FailingExporter:
        def export(self, data):
            raise OSError("disk full")

    monkeypatch.setattr("services.feature_service.FeatureService", DummyFeatureService)
    monkeypatch.setattr("services.testpoint_service.TestPointService", DummyTestPointService)
    monkeypatch.setattr("services.testcase_service.TestCaseService", DummyTestCaseService)
    monkeypatch.setattr(export_api, "ExcelExporter", FailingExporter)

    with pytest.raises(HTTPException) as exc_info:
        await export_api.auto_generate_all(project_id=1, db=db)

    assert exc_info.value.status_code == 500
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()
