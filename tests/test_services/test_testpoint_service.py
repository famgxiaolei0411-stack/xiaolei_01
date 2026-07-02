"""
TestPointService 单元测试
===========================
覆盖: Pydantic 模型校验 / Mock 重试 / 真实 API 四维度覆盖
"""

import json
import pytest
from unittest.mock import MagicMock

from services.testpoint_service import (
    TestPointService,
    TestPointItem,
    TestPointResult,
    TestPointValidationError,
    REQUIRED_CATEGORIES,
)
from services.ai_client import AIClient


# ══════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════

@pytest.fixture
def valid_tp_response() -> dict:
    """有效 LLM 返回 — 四维度全覆盖，8 个测试点。"""
    return {
        "feature_name": "用户登录",
        "test_points": [
            {
                "id": "TP-001",
                "category": "功能测试",
                "description": "输入正确的用户名和密码，点击登录按钮",
                "expected_result": "登录成功，跳转到系统首页",
                "test_data": "用户名: admin, 密码: Test@123",
                "priority": "P0",
            },
            {
                "id": "TP-002",
                "category": "功能测试",
                "description": "勾选'记住我'复选框后登录",
                "expected_result": "登录成功，关闭浏览器后重新打开无需再次登录",
                "test_data": "用户名: admin, 密码: Test@123, 记住我: true",
                "priority": "P1",
            },
            {
                "id": "TP-003",
                "category": "异常测试",
                "description": "用户名为空，点击登录按钮",
                "expected_result": "提示'用户名不能为空'，不跳转",
                "test_data": "用户名: (空), 密码: Test@123",
                "priority": "P1",
            },
            {
                "id": "TP-004",
                "category": "异常测试",
                "description": "密码为空，点击登录按钮",
                "expected_result": "提示'密码不能为空'，不跳转",
                "test_data": "用户名: admin, 密码: (空)",
                "priority": "P1",
            },
            {
                "id": "TP-005",
                "category": "安全测试",
                "description": "用户名输入 SQL 注入代码 ' OR '1'='1",
                "expected_result": "不返回任何用户数据，提示'用户名或密码错误'",
                "test_data": "用户名: ' OR '1'='1, 密码: test",
                "priority": "P0",
            },
            {
                "id": "TP-006",
                "category": "安全测试",
                "description": "用户名输入 XSS 代码 <script>alert(1)</script>",
                "expected_result": "输入被转义，不触发弹窗，页面正常显示",
                "test_data": "用户名: <script>alert(1)</script>, 密码: test",
                "priority": "P0",
            },
            {
                "id": "TP-007",
                "category": "边界值测试",
                "description": "用户名输入 256 个字符",
                "expected_result": "提示'用户名过长，最多 255 字符'",
                "test_data": "用户名: (256个a字符)",
                "priority": "P1",
            },
            {
                "id": "TP-008",
                "category": "边界值测试",
                "description": "用户名输入 1 个字符",
                "expected_result": "正常处理，可登录",
                "test_data": "用户名: a, 密码: Test@123",
                "priority": "P2",
            },
        ],
    }


@pytest.fixture
def missing_security_response() -> dict:
    """缺少安全测试维度的返回。"""
    return {
        "feature_name": "用户登录",
        "test_points": [
            {"id": "TP-001", "category": "功能测试", "description": "正常登录的完整测试场景描述", "expected_result": "登录成功跳转首页", "test_data": "admin/Test@123", "priority": "P0"},
            {"id": "TP-002", "category": "功能测试", "description": "记住我功能的完整测试场景描述", "expected_result": "记住登录状态七天", "test_data": "admin/Test@123", "priority": "P1"},
            {"id": "TP-003", "category": "异常测试", "description": "用户名为空时的完整测试场景", "expected_result": "提示用户名不能为空", "test_data": "", "priority": "P1"},
            {"id": "TP-004", "category": "异常测试", "description": "密码为空时的完整测试场景描述", "expected_result": "提示密码不能为空", "test_data": "", "priority": "P1"},
            {"id": "TP-005", "category": "边界值测试", "description": "用户名超长输入的完整测试场景", "expected_result": "提示用户名过长", "test_data": "256个字符", "priority": "P1"},
            {"id": "TP-006", "category": "边界值测试", "description": "用户名最短输入的完整测试场景", "expected_result": "正常处理请求", "test_data": "1个字符", "priority": "P2"},
        ],
    }


@pytest.fixture
def too_few_response() -> dict:
    """只有 3 个测试点（数量不足）。"""
    return {
        "feature_name": "用户登录",
        "test_points": [
            {"id": "TP-001", "category": "功能测试", "description": "正常登录的完整测试场景描述", "expected_result": "登录成功跳转", "test_data": "admin", "priority": "P0"},
            {"id": "TP-002", "category": "异常测试", "description": "用户名空值的完整测试场景", "expected_result": "提示错误信息", "test_data": "", "priority": "P1"},
            {"id": "TP-003", "category": "安全测试", "description": "SQL注入攻击的完整测试场景", "expected_result": "不泄露数据", "test_data": "1' OR '1", "priority": "P0"},
        ],
    }


# ══════════════════════════════════════════════════════════
# Pydantic 模型测试
# ══════════════════════════════════════════════════════════

class TestTestPointModels:
    """TestPointItem / TestPointResult Schema 校验测试。"""

    def test_item_valid(self) -> None:
        """有效测试点。"""
        item = TestPointItem(
            id="TP-001",
            category="功能测试",
            description="正常登录流程的完整测试场景",
            expected_result="登录成功，跳转首页",
            test_data="admin / Test@123",
            priority="P0",
        )
        assert item.id == "TP-001"
        assert item.category == "功能测试"

    def test_item_invalid_category_raises_error(self) -> None:
        """非法 category 值。"""
        with pytest.raises(Exception):
            TestPointItem(
                id="TP-001",
                category="性能测试",  # 不在四维度内
                description="并发登录压力测试场景描述",
                expected_result="系统稳定",
            )

    def test_item_short_description_raises_error(self) -> None:
        """description 少于 10 字符。"""
        with pytest.raises(Exception):
            TestPointItem(
                id="TP-001",
                category="功能测试",
                description="登录",  # 仅 2 字符（少于 min_length=5）
                expected_result="成功",
            )

    def test_item_invalid_priority_raises_error(self) -> None:
        """非法 priority 值。"""
        with pytest.raises(Exception):
            TestPointItem(
                id="TP-001",
                category="功能测试",
                description="正常登录流程完整测试",
                expected_result="成功",
                priority="invalid",
            )

    def test_result_valid(self, valid_tp_response: dict) -> None:
        """有效完整结果。"""
        result = TestPointResult.model_validate(valid_tp_response)
        assert len(result.test_points) == 8
        assert result.feature_name == "用户登录"

    def test_result_missing_dimension_raises_error(
        self, missing_security_response: dict
    ) -> None:
        """缺少安全测试维度。"""
        with pytest.raises(Exception) as exc_info:
            TestPointResult.model_validate(missing_security_response)
        assert "安全测试" in str(exc_info.value)

    def test_result_too_few_points_raises_error(
        self, too_few_response: dict
    ) -> None:
        """测试点数量不足。"""
        with pytest.raises(Exception) as exc_info:
            TestPointResult.model_validate(too_few_response)
        assert "6" in str(exc_info.value) or "不足" in str(exc_info.value)

    def test_result_duplicate_ids_raises_error(self) -> None:
        """ID 重复。"""
        data = {
            "feature_name": "用户登录",
            "test_points": [
                {"id": "TP-001", "category": "功能测试", "description": "测试点A的完整测试场景描述", "expected_result": "操作成功", "priority": "P0"},
                {"id": "TP-001", "category": "异常测试", "description": "测试点B的完整测试场景描述", "expected_result": "操作失败", "priority": "P1"},
                {"id": "TP-002", "category": "安全测试", "description": "测试点C的完整测试场景描述", "expected_result": "安全防护生效", "priority": "P0"},
                {"id": "TP-003", "category": "边界值测试", "description": "测试点D的完整测试场景描述", "expected_result": "边界处理正确", "priority": "P1"},
                {"id": "TP-004", "category": "功能测试", "description": "测试点E的完整测试场景描述", "expected_result": "操作成功返回", "priority": "P2"},
                {"id": "TP-005", "category": "异常测试", "description": "测试点F的完整测试场景描述", "expected_result": "异常处理正确", "priority": "P2"},
            ],
        }
        with pytest.raises(Exception) as exc_info:
            TestPointResult.model_validate(data)
        assert "重复" in str(exc_info.value)

    def test_result_model_dump_format(self, valid_tp_response: dict) -> None:
        """model_dump 输出格式。"""
        result = TestPointResult.model_validate(valid_tp_response)
        d = result.model_dump()

        assert "feature_name" in d
        assert "test_points" in d
        assert isinstance(d["test_points"], list)
        for tp in d["test_points"]:
            assert set(tp.keys()) == {
                "id", "category", "description",
                "expected_result", "test_data", "priority",
            }
        # 验证四维度覆盖
        categories = {tp["category"] for tp in d["test_points"]}
        assert categories == REQUIRED_CATEGORIES


# ══════════════════════════════════════════════════════════
# FeatureService Mock 测试
# ══════════════════════════════════════════════════════════

class TestTestPointServiceWithMock:
    """Mock DeepSeek API 测试。"""

    class FailingSkillOrchestrator:
        """测试用：模拟 Skill 编排失败。"""

        def compose_prompt(self, base_prompt, context):
            raise RuntimeError("skill failed")

    def test_generate_success(self, valid_tp_response: dict) -> None:
        """正常生成成功。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = valid_tp_response

        service = TestPointService(ai_client=mock_ai)
        result = service.generate("用户登录", "用户验证身份后进入系统")

        assert len(result.test_points) == 8
        assert result.feature_name == "用户登录"
        # 确认四维度全覆盖
        categories = {tp.category for tp in result.test_points}
        assert categories == REQUIRED_CATEGORIES
        assert mock_ai.chat_json.call_count == 1

    def test_generate_first_prompt_is_enhanced_by_default_skills(
        self, valid_tp_response: dict
    ) -> None:
        """首次生成 Prompt 会追加默认 Skill 片段。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = valid_tp_response

        service = TestPointService(ai_client=mock_ai)
        service.generate("用户登录", "用户验证身份后进入系统")

        first_call = mock_ai.chat_json.call_args_list[0].kwargs
        user_prompt = first_call["user_prompt"]
        assert "## 边界值分析" in user_prompt
        assert "空值" in user_prompt
        assert "最小值" in user_prompt
        assert "最大值" in user_prompt
        assert "边界前一个值" in user_prompt
        assert "## 等价类划分" in user_prompt
        assert "有效等价类" in user_prompt
        assert "无效等价类" in user_prompt
        assert "输入类型" in user_prompt
        assert "业务规则" in user_prompt

    def test_generate_uses_base_prompt_when_skill_fails(
        self, valid_tp_response: dict
    ) -> None:
        """Skill 增强失败时降级为原始 Prompt，主流程继续成功。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = valid_tp_response

        service = TestPointService(
            ai_client=mock_ai,
            skill_orchestrator=self.FailingSkillOrchestrator(),
        )
        result = service.generate("用户登录", "用户验证身份后进入系统")

        first_call = mock_ai.chat_json.call_args_list[0].kwargs
        assert result.feature_name == "用户登录"
        assert "## 边界值分析" not in first_call["user_prompt"]
        assert "## 等价类划分" not in first_call["user_prompt"]
        assert mock_ai.chat_json.call_count == 1

    def test_generate_retry_on_json_error(
        self, valid_tp_response: dict
    ) -> None:
        """JSON 解析失败 → 重试成功。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.side_effect = [
            ValueError("无法解析 JSON"),
            valid_tp_response,
        ]

        service = TestPointService(ai_client=mock_ai)
        result = service.generate("用户登录")

        assert len(result.test_points) == 8
        assert mock_ai.chat_json.call_count == 2

    def test_generate_retry_on_schema_error(
        self, missing_security_response: dict, valid_tp_response: dict
    ) -> None:
        """Schema 校验失败（缺维度） → 重试成功。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.side_effect = [
            missing_security_response,
            valid_tp_response,
        ]

        service = TestPointService(ai_client=mock_ai)
        result = service.generate("用户登录")

        assert len(result.test_points) == 8
        assert mock_ai.chat_json.call_count == 2

    def test_generate_exhausted_retries(
        self, missing_security_response: dict
    ) -> None:
        """重试耗尽抛出异常。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = missing_security_response

        service = TestPointService(ai_client=mock_ai)

        with pytest.raises(TestPointValidationError):
            service.generate("用户登录")

        assert mock_ai.chat_json.call_count == 3

    def test_generate_empty_name_raises_error(self) -> None:
        """空功能点名称。"""
        service = TestPointService(ai_client=MagicMock(spec=AIClient))
        with pytest.raises(ValueError):
            service.generate("")

    def test_generate_retry_prompt_has_feedback(
        self, missing_security_response: dict, valid_tp_response: dict
    ) -> None:
        """重试 Prompt 包含错误反馈。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.side_effect = [
            missing_security_response,
            valid_tp_response,
        ]

        service = TestPointService(ai_client=mock_ai)
        service.generate("用户登录")

        second_call = mock_ai.chat_json.call_args_list[1].kwargs
        assert "上次输出" in second_call["user_prompt"]
        assert "用户登录" in second_call["user_prompt"]
        assert "## 边界值分析" not in second_call["user_prompt"]
        assert "## 等价类划分" not in second_call["user_prompt"]

    def test_generate_corrects_feature_name_mismatch(
        self, valid_tp_response: dict
    ) -> None:
        """LLM 返回的 feature_name 不匹配时自动修正。"""
        response = dict(valid_tp_response)
        response["feature_name"] = "登录模块"  # 故意不一致

        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = response

        service = TestPointService(ai_client=mock_ai)
        result = service.generate("用户登录")

        # 应修正为输入值
        assert result.feature_name == "用户登录"

    def test_generate_to_dict_format(self, valid_tp_response: dict) -> None:
        """extract_to_dict 格式正确。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = valid_tp_response

        service = TestPointService(ai_client=mock_ai)
        result = service.generate_to_dict("用户登录")

        assert isinstance(result, dict)
        assert result["feature_name"] == "用户登录"
        assert len(result["test_points"]) == 8


# ══════════════════════════════════════════════════════════
# 真实 API 集成测试
# ══════════════════════════════════════════════════════════

@pytest.mark.integration
class TestTestPointServiceWithRealAPI:
    """真实 DeepSeek API 的集成测试。

    运行方式:
        pytest tests/test_services/test_testpoint_service.py -v -m integration
    """

    def test_generate_login_feature(self) -> None:
        """测试为「用户登录」生成测试点 — 四维度覆盖。"""
        service = TestPointService()
        result = service.generate(
            "用户登录",
            "用户输入用户名和密码，系统验证成功后跳转首页。"
            "连续5次失败锁定30分钟。支持记住我功能。",
        )

        # ── 基础校验 ──────────────────────────────
        assert isinstance(result, TestPointResult)
        assert len(result.test_points) >= 6
        assert result.feature_name == "用户登录"

        # ── 四维度覆盖 ────────────────────────────
        categories = {tp.category for tp in result.test_points}
        missing = REQUIRED_CATEGORIES - categories
        assert not missing, f"缺少维度: {missing}"

        # ── 内容正确性 ────────────────────────────
        descriptions = [tp.description for tp in result.test_points]
        all_desc = " ".join(descriptions)

        # 安全测试点应包含 SQL 注入或 XSS
        security_tps = [
            tp for tp in result.test_points if tp.category == "安全测试"
        ]
        assert len(security_tps) >= 1
        security_text = " ".join(tp.description for tp in security_tps)
        assert (
            "SQL" in security_text
            or "注入" in security_text
            or "XSS" in security_text
            or "script" in security_text.lower()
        ), f"安全测试点应包含注入/XSS 场景: {security_text}"

    def test_generate_registration_feature(self) -> None:
        """测试为「用户注册」生成测试点。"""
        service = TestPointService()
        result = service.generate(
            "用户注册",
            "用户通过手机号或邮箱注册，需填写用户名、密码（8-20位含大小写字母数字）。"
            "手机号和邮箱需验证唯一性。",
        )

        assert len(result.test_points) >= 6

        categories = {tp.category for tp in result.test_points}
        assert categories == REQUIRED_CATEGORIES

    def test_generate_to_dict_real_api(self) -> None:
        """真实 API 测试 generate_to_dict 输出。"""
        service = TestPointService()
        result = service.generate_to_dict(
            "密码重置",
            "用户通过邮箱验证码重置密码，新密码不可与最近3次相同",
        )

        assert isinstance(result, dict)
        assert result["feature_name"] == "密码重置"
        assert len(result["test_points"]) >= 6

        for tp in result["test_points"]:
            assert "id" in tp
            assert tp["category"] in REQUIRED_CATEGORIES
            assert len(tp["description"]) >= 5
            assert len(tp["expected_result"]) >= 5
