"""
FeatureService 单元测试
=========================
覆盖场景：正常提取、Schema 校验、重试逻辑、异常路径、Pydantic 模型。
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from services.feature_service import (
    FeatureService,
    FeatureItem,
    FeatureResult,
    FeatureValidationError,
)
from services.ai_client import AIClient


# ══════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════

@pytest.fixture
def valid_llm_response() -> dict:
    """模拟 LLM 的有效 JSON 返回。"""
    return {
        "features": [
            {"name": "用户注册", "description": "用户通过手机号或邮箱注册账号"},
            {"name": "用户登录", "description": "用户使用用户名和密码登录系统"},
            {"name": "密码修改", "description": "登录用户修改密码，需验证原密码"},
        ]
    }


@pytest.fixture
def invalid_json_response() -> dict:
    """模拟 LLM 返回格式错误的 JSON — features 为空数组。"""
    return {"features": []}


@pytest.fixture
def missing_field_response() -> dict:
    """模拟 LLM 返回缺少 description 字段。"""
    return {
        "features": [
            {"name": "用户登录"},
            # 缺少 description
        ]
    }


@pytest.fixture
def real_requirement_text() -> str:
    """真实需求文档文本（用于真实 API 测试）。"""
    return """
用户管理系统需求规格说明书

## 1. 用户注册
用户可以通过手机号或邮箱进行注册。
注册时需要填写用户名、密码、确认密码。
密码长度要求 8-20 位，包含大小写字母和数字。
注册成功后跳转到登录页面。
手机号和邮箱需要验证唯一性，已注册的不能重复注册。

## 2. 用户登录
用户可以通过用户名+密码进行登录。
连续输错 5 次密码，账号锁定 30 分钟。
支持"记住我"功能，有效期 7 天。
登录成功后跳转到系统首页。

## 3. 密码修改
登录用户可以修改自己的密码。
需要先输入原密码验证身份。
新密码不能与最近 3 次密码相同。
密码修改成功后发送短信通知用户。

## 4. 账号注销
用户可以申请注销账号。
注销前需验证身份（输入密码）。
注销后有 15 天冷静期，期间可撤销。
冷静期过后账号永久删除。
"""


# ══════════════════════════════════════════════════════════
# Pydantic 模型测试
# ══════════════════════════════════════════════════════════

class TestFeatureModels:
    """FeatureItem / FeatureResult 模型测试。"""

    def test_feature_item_valid(self) -> None:
        """测试 FeatureItem 有效数据。"""
        item = FeatureItem(name="用户登录", description="用户登录系统")
        assert item.name == "用户登录"
        assert item.description == "用户登录系统"

    def test_feature_item_empty_name_raises_error(self) -> None:
        """测试 name 为空字符串时校验失败。"""
        with pytest.raises(Exception):
            FeatureItem(name="", description="描述")

    def test_feature_item_name_too_long_raises_error(self) -> None:
        """测试 name 超过 200 字符时校验失败。"""
        with pytest.raises(Exception):
            FeatureItem(name="A" * 201, description="描述")

    def test_feature_item_empty_description_raises_error(self) -> None:
        """测试 description 为空字符串时校验失败。"""
        with pytest.raises(Exception):
            FeatureItem(name="功能", description="")

    def test_feature_result_valid(self, valid_llm_response: dict) -> None:
        """测试 FeatureResult 有效数据。"""
        result = FeatureResult.model_validate(valid_llm_response)
        assert len(result.features) == 3
        assert result.features[0].name == "用户注册"

    def test_feature_result_empty_features_raises_error(
        self, invalid_json_response: dict
    ) -> None:
        """测试 features 为空数组时校验失败。"""
        with pytest.raises(Exception):
            FeatureResult.model_validate(invalid_json_response)

    def test_feature_result_missing_field_raises_error(
        self, missing_field_response: dict
    ) -> None:
        """测试缺少必填字段时校验失败。"""
        with pytest.raises(Exception):
            FeatureResult.model_validate(missing_field_response)

    def test_model_dump_format(self, valid_llm_response: dict) -> None:
        """测试 model_dump 输出格式符合规范。"""
        result = FeatureResult.model_validate(valid_llm_response)
        d = result.model_dump()

        assert "features" in d
        assert isinstance(d["features"], list)
        assert len(d["features"]) == 3
        # 每个 feature 只有 name 和 description
        for item in d["features"]:
            assert set(item.keys()) == {"name", "description"}


# ══════════════════════════════════════════════════════════
# FeatureService Mock 测试
# ══════════════════════════════════════════════════════════

class TestFeatureServiceWithMock:
    """使用 Mock 测试 FeatureService（不调用真实 API）。"""

    def test_extract_success_first_attempt(
        self, valid_llm_response: dict
    ) -> None:
        """测试首次调用成功场景。"""
        # ── Mock AIClient ─────────────────────────
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = valid_llm_response

        service = FeatureService(ai_client=mock_ai)
        result = service.extract("用户注册和登录功能需求文档")

        assert len(result.features) == 3
        assert result.features[0].name == "用户注册"
        # 只调用了一次
        assert mock_ai.chat_json.call_count == 1

    def test_extract_retry_on_json_parse_error(
        self, valid_llm_response: dict
    ) -> None:
        """测试 JSON 解析失败后重试成功。"""
        mock_ai = MagicMock(spec=AIClient)

        # 第 1 次：返回无法解析的内容
        # 第 2 次：返回有效 JSON
        mock_ai.chat_json.side_effect = [
            ValueError("无法解析为 JSON"),
            valid_llm_response,
        ]

        service = FeatureService(ai_client=mock_ai)
        result = service.extract("用户管理系统需求文档内容描述，包含注册和登录功能")

        assert len(result.features) == 3
        # 调用了 2 次
        assert mock_ai.chat_json.call_count == 2

    def test_extract_retry_on_schema_validation_error(
        self, invalid_json_response: dict, valid_llm_response: dict
    ) -> None:
        """测试 Schema 校验失败后重试成功。"""
        mock_ai = MagicMock(spec=AIClient)

        # 第 1 次：features 为空数组（Schema 校验失败）
        # 第 2 次：有效数据
        mock_ai.chat_json.side_effect = [
            invalid_json_response,
            valid_llm_response,
        ]

        service = FeatureService(ai_client=mock_ai)
        result = service.extract("用户管理系统需求文档内容描述，包含注册和登录功能")

        assert len(result.features) == 3
        assert mock_ai.chat_json.call_count == 2

    def test_extract_retry_exhausted_raises_error(
        self, invalid_json_response: dict
    ) -> None:
        """测试重试耗尽后抛出 FeatureValidationError。"""
        mock_ai = MagicMock(spec=AIClient)
        # 始终返回空 features
        mock_ai.chat_json.return_value = invalid_json_response

        service = FeatureService(ai_client=mock_ai)

        with pytest.raises(FeatureValidationError) as exc_info:
            service.extract("用户管理系统需求文档内容描述，包含注册和登录功能")

        assert "重试" in str(exc_info.value.message)
        assert mock_ai.chat_json.call_count == 3  # MAX_VALIDATION_RETRIES

    def test_extract_retry_prompt_includes_error_feedback(
        self, invalid_json_response: dict, valid_llm_response: dict
    ) -> None:
        """测试重试 Prompt 包含上次的错误反馈。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.side_effect = [
            invalid_json_response,
            valid_llm_response,
        ]

        service = FeatureService(ai_client=mock_ai)
        service.extract("用户管理系统需求文档内容描述，包含注册和登录功能")

        # 取第 2 次调用的 prompt 参数
        second_call_kwargs = mock_ai.chat_json.call_args_list[1].kwargs
        user_prompt = second_call_kwargs["user_prompt"]

        assert "上次输出" in user_prompt
        assert "用户管理系统需求文档内容描述，包含注册和登录功能" in user_prompt

    def test_extract_short_input_raises_error(self) -> None:
        """测试输入文本过短抛出 ValueError。"""
        mock_ai = MagicMock(spec=AIClient)
        service = FeatureService(ai_client=mock_ai)

        with pytest.raises(ValueError) as exc_info:
            service.extract("短")
        assert "过短" in str(exc_info.value)
        # 不应调用 AI
        mock_ai.chat_json.assert_not_called()

    def test_extract_empty_input_raises_error(self) -> None:
        """测试空输入。"""
        service = FeatureService(ai_client=MagicMock(spec=AIClient))

        with pytest.raises(ValueError):
            service.extract("")

    def test_extract_to_dict_returns_correct_format(
        self, valid_llm_response: dict
    ) -> None:
        """测试 extract_to_dict 返回标准字典格式。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = valid_llm_response

        service = FeatureService(ai_client=mock_ai)
        result = service.extract_to_dict("用户管理系统需求文档内容描述，包含注册和登录功能")

        assert isinstance(result, dict)
        assert "features" in result
        assert isinstance(result["features"], list)
        assert len(result["features"]) == 3

    def test_extract_preserves_prompt_structure(self) -> None:
        """测试 Prompt 结构完整性 — System 和 User Prompt 分开传递。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = {
            "features": [{"name": "测试", "description": "测试描述"}]
        }

        service = FeatureService(ai_client=mock_ai)
        service.extract("这是一段足够长的需求文档文本内容用于测试")

        # 验证调用参数结构
        call_kwargs = mock_ai.chat_json.call_args.kwargs
        assert "system_prompt" in call_kwargs
        assert "user_prompt" in call_kwargs
        assert len(call_kwargs["system_prompt"]) > 0
        assert "这是一段足够长的需求文档文本内容用于测试" in call_kwargs["user_prompt"]


# ══════════════════════════════════════════════════════════
# FeatureService 真实 API 测试（需要 DeepSeek Key）
# ══════════════════════════════════════════════════════════

@pytest.mark.integration
class TestFeatureServiceWithRealAPI:
    """使用真实 DeepSeek API 的集成测试。

    运行方式:
        pytest tests/test_services/test_feature_service.py -v -m integration
    """

    def test_extract_with_real_api(self, real_requirement_text: str) -> None:
        """测试真实 API 调用 — 提取功能点并校验结果。

        验证：
        1. API 调用成功返回
        2. 结果通过 Pydantic 校验
        3. 提取到的功能点包含预期内容
        """
        service = FeatureService()
        result = service.extract(real_requirement_text)

        # ── 基础校验 ──────────────────────────────
        assert isinstance(result, FeatureResult)
        assert len(result.features) >= 3  # 至少 3 个功能点

        # ── 内容校验 ──────────────────────────────
        feature_names = [f.name for f in result.features]
        feature_descs = [f.description for f in result.features]
        all_text = " ".join(feature_names) + " " + " ".join(feature_descs)

        # 关键功能点应该出现
        assert any("注册" in name for name in feature_names), (
            f"应包含注册相关功能点，实际: {feature_names}"
        )
        assert any("登录" in name for name in feature_names), (
            f"应包含登录相关功能点，实际: {feature_names}"
        )

        # 关键业务规则应该出现在描述中
        assert any("8" in desc and "20" in desc for desc in feature_descs), (
            "应包含密码长度限制 8-20"
        )
        assert any("5" in desc and "30" in desc for desc in feature_descs), (
            "应包含登录锁定策略（5次/30分钟）"
        )

    def test_extract_to_dict_with_real_api(
        self, real_requirement_text: str
    ) -> None:
        """测试 extract_to_dict 真实 API 调用。"""
        service = FeatureService()
        result = service.extract_to_dict(real_requirement_text)

        assert isinstance(result, dict)
        assert "features" in result
        assert len(result["features"]) >= 3
        for item in result["features"]:
            assert "name" in item
            assert "description" in item
            assert len(item["name"]) > 0
            assert len(item["description"]) > 0

    def test_extract_simple_text_real_api(self) -> None:
        """测试简单需求文本的真实 API 提取。"""
        service = FeatureService()
        result = service.extract(
            "系统需要实现用户登录功能。"
            "用户输入用户名和密码后点击登录按钮。"
            "系统验证用户名密码正确后跳转到首页。"
            "如果密码错误则提示'用户名或密码错误'。"
        )

        assert len(result.features) >= 1
        # 应该提取到登录相关功能
        names = [f.name for f in result.features]
        assert any("登录" in name for name in names)
