from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.api import batch as batch_api
from backend.api.batch import BatchGenerateRequest
import services.testpoint_service as testpoint_service_module


@pytest.mark.asyncio
async def test_batch_generate_rolls_back_project_when_testpoint_generation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    project = SimpleNamespace(
        name="示例项目",
        doc_content="用户可以登录系统，并支持密码错误提示。",
        doc_filename="req.txt",
    )
    monkeypatch.setattr(batch_api, "get_project", AsyncMock(return_value=project))

    save_features = AsyncMock()
    save_testpoints = AsyncMock()
    save_testcases = AsyncMock()
    update_status = AsyncMock()
    monkeypatch.setattr("backend.db.crud.save_features", save_features)
    monkeypatch.setattr("backend.db.crud.save_testpoints", save_testpoints)
    monkeypatch.setattr("backend.db.crud.save_testcases", save_testcases)
    monkeypatch.setattr("backend.db.crud.update_project_status", update_status)

    monkeypatch.setattr("services.ai_client.get_ai_client", lambda: object())
    monkeypatch.setattr(
        "services.document_classifier.classify_document",
        lambda content: SimpleNamespace(doc_type="requirement", mode="functional", confidence=0.95),
    )

    class DummyParser:
        def _chunk_text(self, content: str):
            return [SimpleNamespace(content=content)]

    class DummyFeatureService:
        def __init__(self, ai_client) -> None:
            self.ai_client = ai_client

        def extract(self, content: str):
            return SimpleNamespace(
                features=[SimpleNamespace(name="用户登录", description="用户输入账号密码登录")]
            )

    class FailingTestPointService:
        def __init__(self, ai_client=None) -> None:
            self.ai_client = ai_client

        def generate(self, feature_name: str, feature_description: str = ""):
            raise testpoint_service_module.TestPointValidationError("测试点 Schema 校验失败")

    monkeypatch.setattr("services.document_parser.DocumentParser", DummyParser)
    monkeypatch.setattr("services.feature_service.FeatureService", DummyFeatureService)
    monkeypatch.setattr("services.testpoint_service.TestPointService", FailingTestPointService)

    response = await batch_api.batch_generate(
        BatchGenerateRequest(project_ids=[1]),
        db=db,
    )

    assert response.ok is True
    result = response.data["results"][0]
    assert result["ok"] is False
    assert "测试点生成失败" in result["error"]
    save_features.assert_awaited_once()
    save_testpoints.assert_not_awaited()
    save_testcases.assert_not_awaited()
    db.rollback.assert_awaited_once()
    db.commit.assert_awaited_once()
