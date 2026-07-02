"""
TestCaseService 单元测试
==========================
覆盖: Pydantic 模型校验 / Mock 重试 / 真实 API 行业标准验证
"""

import json
import pytest
from unittest.mock import MagicMock

from services.testcase_service import (
    TestCaseService,
    TestCaseItem,
    TestCaseResult,
    TestCaseValidationError,
)
from services.ai_client import AIClient


# ══════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════

@pytest.fixture
def sample_test_points() -> list[dict]:
    """示例测试点（用户登录）。"""
    return [
        {"category": "功能测试", "description": "正常用户名密码登录"},
        {"category": "异常测试", "description": "用户名为空点击登录"},
        {"category": "异常测试", "description": "密码为空点击登录"},
        {"category": "安全测试", "description": "SQL注入 ' OR '1'='1"},
        {"category": "安全测试", "description": "XSS <script>alert(1)</script>"},
        {"category": "边界值测试", "description": "用户名输入256个字符"},
    ]


@pytest.fixture
def valid_llm_response_list() -> list:
    """LLM 返回的数组格式（正确）。"""
    return [
        {
            "id": "TC-LOGIN-001",
            "title": "用户登录 - 正常用户名密码 - 登录成功",
            "precondition": "系统已部署，测试账号 admin/Test@123 已注册且未锁定",
            "steps": [
                "1. 打开登录页面 http://localhost/login",
                "2. 在用户名输入框输入 'admin'",
                "3. 在密码输入框输入 'Test@123'",
                "4. 点击「登录」按钮",
                "5. 验证页面跳转到系统首页",
            ],
            "expected_result": "登录成功，页面跳转到 /home，右上角显示用户名 'admin'",
        },
        {
            "id": "TC-LOGIN-002",
            "title": "用户登录 - 用户名为空 - 提示错误",
            "precondition": "系统已部署，打开登录页面",
            "steps": [
                "1. 打开登录页面 http://localhost/login",
                "2. 用户名输入框保持为空",
                "3. 在密码输入框输入 'Test@123'",
                "4. 点击「登录」按钮",
                "5. 验证页面显示错误提示",
            ],
            "expected_result": "登录失败，页面显示'用户名不能为空'，不跳转",
        },
        {
            "id": "TC-LOGIN-003",
            "title": "用户登录 - 密码为空 - 提示错误",
            "precondition": "系统已部署，打开登录页面",
            "steps": [
                "1. 打开登录页面",
                "2. 在用户名输入框输入 'admin'",
                "3. 密码输入框保持为空",
                "4. 点击「登录」按钮",
                "5. 验证页面显示错误提示",
            ],
            "expected_result": "登录失败，页面显示'密码不能为空'",
        },
        {
            "id": "TC-LOGIN-004",
            "title": "用户登录 - SQL注入攻击 - 不泄露数据",
            "precondition": "系统已部署，打开登录页面",
            "steps": [
                "1. 打开登录页面",
                "2. 在用户名输入框输入 \"' OR '1'='1\"",
                "3. 在密码输入框输入 'test'",
                "4. 点击「登录」按钮",
                "5. 验证系统响应",
            ],
            "expected_result": "登录失败，提示'用户名或密码错误'，不返回任何用户数据",
        },
        {
            "id": "TC-LOGIN-005",
            "title": "用户登录 - XSS攻击 - 脚本被转义",
            "precondition": "系统已部署，打开登录页面",
            "steps": [
                "1. 打开登录页面",
                "2. 在用户名输入框输入 '<script>alert(1)</script>'",
                "3. 在密码输入框输入 'test'",
                "4. 点击「登录」按钮",
                "5. 检查页面是否执行脚本",
            ],
            "expected_result": "登录失败，脚本被转义为纯文本显示，不触发弹窗",
        },
        {
            "id": "TC-LOGIN-006",
            "title": "用户登录 - 用户名超长 - 提示过长",
            "precondition": "系统已部署，用户名字段限制255字符",
            "steps": [
                "1. 打开登录页面",
                "2. 在用户名输入框粘贴256个字符",
                "3. 在密码输入框输入 'Test@123'",
                "4. 点击「登录」按钮",
                "5. 验证系统响应",
            ],
            "expected_result": "登录失败，提示'用户名过长，最多255字符'",
        },
    ]


@pytest.fixture
def valid_llm_response_dict(valid_llm_response_list: list) -> dict:
    """LLM 返回的字典格式 {"testcases": [...]}。"""
    return {"testcases": valid_llm_response_list}


@pytest.fixture
def invalid_response_no_steps() -> list:
    """steps 为空数组（不规范）。"""
    return [
        {
            "id": "TC-001",
            "title": "测试 - 测试 - 测试",
            "precondition": "无",
            "steps": [],
            "expected_result": "成功",
        },
        {
            "id": "TC-002",
            "title": "测试2",
            "precondition": "无",
            "steps": ["1. 步骤一"],
            "expected_result": "成功",
        },
    ]


@pytest.fixture
def invalid_response_duplicate_ids() -> list:
    """ID 重复。"""
    return [
        {
            "id": "TC-001",
            "title": "用户登录 - 正常 - 成功",
            "precondition": "无",
            "steps": ["1. 打开页面", "2. 输入用户名", "3. 点击登录"],
            "expected_result": "登录成功，跳转首页",
        },
        {
            "id": "TC-001",
            "title": "用户登录 - 异常 - 失败",
            "precondition": "无",
            "steps": ["1. 打开页面", "2. 不输入用户名", "3. 点击登录"],
            "expected_result": "提示用户名不能为空",
        },
    ]


# ══════════════════════════════════════════════════════════
# Pydantic 模型测试
# ══════════════════════════════════════════════════════════

class TestTestCaseModels:
    """TestCaseItem / TestCaseResult Schema 校验测试。"""

    def test_item_valid(self) -> None:
        """有效用例通过校验。"""
        item = TestCaseItem(
            id="TC-LOGIN-001",
            title="用户登录 - 正常密码 - 登录成功",
            precondition="测试账号已注册",
            steps=[
                "1. 打开登录页面",
                "2. 输入用户名 'admin'",
                "3. 输入密码 'Test@123'",
                "4. 点击登录按钮",
            ],
            expected_result="登录成功，跳转首页",
        )
        assert item.id == "TC-LOGIN-001"
        assert len(item.steps) == 4

    def test_item_empty_steps_raises_error(self) -> None:
        """steps 为空列表时校验失败。"""
        with pytest.raises(Exception):
            TestCaseItem(
                id="TC-001",
                title="测试用例标题",
                steps=[],
                expected_result="预期结果描述",
            )

    def test_item_short_expected_raises_error(self) -> None:
        """expected_result 过短（< 5 字符）。"""
        with pytest.raises(Exception):
            TestCaseItem(
                id="TC-001",
                title="测试用例标题足够长",
                steps=["1. 步骤一", "2. 步骤二"],
                expected_result="OK",  # 仅 2 字符
            )

    def test_item_too_many_steps_raises_error(self) -> None:
        """steps 超过 20 个。"""
        with pytest.raises(Exception):
            TestCaseItem(
                id="TC-001",
                title="测试用例标题足够长",
                steps=[f"{i}. 步骤{i}" for i in range(1, 22)],  # 21 步
                expected_result="预期结果描述信息",
            )

    def test_item_title_too_short_raises_error(self) -> None:
        """title 过短。"""
        with pytest.raises(Exception):
            TestCaseItem(
                id="TC-001",
                title="ab",  # 仅 2 字符
                steps=["1. 步骤一", "2. 步骤二"],
                expected_result="预期结果描述信息",
            )

    def test_item_default_precondition(self) -> None:
        """未提供 precondition 时取默认值。"""
        item = TestCaseItem(
            id="TC-001",
            title="测试用例标题足够长",
            steps=["1. 步骤一", "2. 步骤二"],
            expected_result="预期结果描述信息",
        )
        assert item.precondition == "无"

    def test_result_valid(self, valid_llm_response_list: list) -> None:
        """有效用例列表通过校验。"""
        result = TestCaseResult.model_validate(
            {"testcases": valid_llm_response_list}
        )
        assert len(result.testcases) == 6

    def test_result_duplicate_ids_raises_error(
        self, invalid_response_duplicate_ids: list
    ) -> None:
        """ID 重复时校验失败。"""
        with pytest.raises(Exception) as exc_info:
            TestCaseResult.model_validate(
                {"testcases": invalid_response_duplicate_ids}
            )
        assert "重复" in str(exc_info.value)

    def test_result_empty_list_raises_error(self) -> None:
        """空列表校验失败。"""
        with pytest.raises(Exception):
            TestCaseResult.model_validate({"testcases": []})


# ══════════════════════════════════════════════════════════
# TestCaseService Mock 测试
# ══════════════════════════════════════════════════════════

class TestTestCaseServiceWithMock:
    """Mock DeepSeek API 测试。"""

    class FailingSkillOrchestrator:
        """测试用：模拟 Skill 编排失败。"""

        def compose_prompt(self, base_prompt, context):
            raise RuntimeError("skill failed")

    def test_generate_list_format(
        self, sample_test_points: list, valid_llm_response_list: list
    ) -> None:
        """LLM 返回数组格式 → 正常生成。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = valid_llm_response_list

        service = TestCaseService(ai_client=mock_ai)
        result = service.generate("用户登录", sample_test_points)

        assert len(result) == 6
        assert result[0].id == "TC-LOGIN-001"
        assert len(result[0].steps) >= 2
        assert mock_ai.chat_json.call_count == 1

    def test_generate_first_prompt_is_enhanced_by_default_skills(
        self, sample_test_points: list, valid_llm_response_list: list
    ) -> None:
        """首次生成 Prompt 会追加默认 Skill 片段。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = valid_llm_response_list

        service = TestCaseService(ai_client=mock_ai)
        service.generate("用户登录", sample_test_points)

        first_call = mock_ai.chat_json.call_args_list[0].kwargs
        user_prompt = first_call["user_prompt"]
        assert "## 边界值分析" in user_prompt
        assert "空值" in user_prompt
        assert "最小值" in user_prompt
        assert "最大值" in user_prompt
        assert "## 等价类划分" in user_prompt
        assert "有效等价类" in user_prompt
        assert "无效等价类" in user_prompt
        assert "输入类型" in user_prompt
        assert "业务规则" in user_prompt

    def test_generate_uses_base_prompt_when_skill_fails(
        self, sample_test_points: list, valid_llm_response_list: list
    ) -> None:
        """Skill 增强失败时降级为原始 Prompt，主流程继续成功。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = valid_llm_response_list

        service = TestCaseService(
            ai_client=mock_ai,
            skill_orchestrator=self.FailingSkillOrchestrator(),
        )
        result = service.generate("用户登录", sample_test_points)

        first_call = mock_ai.chat_json.call_args_list[0].kwargs
        assert len(result) == 6
        assert "## 边界值分析" not in first_call["user_prompt"]
        assert "## 等价类划分" not in first_call["user_prompt"]
        assert mock_ai.chat_json.call_count == 1

    def test_generate_dict_format(
        self, sample_test_points: list, valid_llm_response_dict: dict
    ) -> None:
        """LLM 返回 {"testcases": [...]} 格式 → 正常处理。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = valid_llm_response_dict

        service = TestCaseService(ai_client=mock_ai)
        result = service.generate("用户登录", sample_test_points)

        assert len(result) == 6
        assert mock_ai.chat_json.call_count == 1

    def test_generate_retry_on_validation_error(
        self,
        sample_test_points: list,
        invalid_response_no_steps: list,
        valid_llm_response_list: list,
    ) -> None:
        """Schema 校验失败 → 重试成功。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.side_effect = [
            invalid_response_no_steps,
            valid_llm_response_list,
        ]

        service = TestCaseService(ai_client=mock_ai)
        result = service.generate("用户登录", sample_test_points)

        assert len(result) == 6
        assert mock_ai.chat_json.call_count == 2

    def test_generate_retry_on_json_error(
        self, sample_test_points: list, valid_llm_response_list: list
    ) -> None:
        """JSON 解析失败 → 重试成功。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.side_effect = [
            ValueError("无法解析 JSON"),
            valid_llm_response_list,
        ]

        service = TestCaseService(ai_client=mock_ai)
        result = service.generate("用户登录", sample_test_points)

        assert len(result) == 6
        assert mock_ai.chat_json.call_count == 2

    def test_generate_exhausted_retries(
        self, sample_test_points: list, invalid_response_no_steps: list
    ) -> None:
        """重试耗尽抛出异常。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = invalid_response_no_steps

        service = TestCaseService(ai_client=mock_ai)

        with pytest.raises(TestCaseValidationError):
            service.generate("用户登录", sample_test_points)

        assert mock_ai.chat_json.call_count == 3

    def test_generate_empty_feature_name_raises_error(
        self, sample_test_points: list
    ) -> None:
        """空名称抛 ValueError。"""
        service = TestCaseService(ai_client=MagicMock(spec=AIClient))
        with pytest.raises(ValueError):
            service.generate("", sample_test_points)

    def test_generate_empty_test_points_raises_error(self) -> None:
        """空测试点列表抛 ValueError。"""
        service = TestCaseService(ai_client=MagicMock(spec=AIClient))
        with pytest.raises(ValueError):
            service.generate("用户登录", [])

    def test_generate_retry_prompt_has_feedback(
        self,
        sample_test_points: list,
        invalid_response_no_steps: list,
        valid_llm_response_list: list,
    ) -> None:
        """重试 Prompt 包含错误反馈。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.side_effect = [
            invalid_response_no_steps,
            valid_llm_response_list,
        ]

        service = TestCaseService(ai_client=mock_ai)
        service.generate("用户登录", sample_test_points)

        second_call = mock_ai.chat_json.call_args_list[1].kwargs
        assert "上次输出" in second_call["user_prompt"]
        assert "用户登录" in second_call["user_prompt"]
        assert "## 边界值分析" not in second_call["user_prompt"]
        assert "## 等价类划分" not in second_call["user_prompt"]

    def test_generate_to_dict(
        self, sample_test_points: list, valid_llm_response_list: list
    ) -> None:
        """generate_to_dict 输出格式正确。"""
        mock_ai = MagicMock(spec=AIClient)
        mock_ai.chat_json.return_value = valid_llm_response_list

        service = TestCaseService(ai_client=mock_ai)
        result = service.generate_to_dict("用户登录", sample_test_points)

        assert isinstance(result, list)
        assert len(result) == 6
        for tc in result:
            assert "id" in tc
            assert "title" in tc
            assert "precondition" in tc
            assert "steps" in tc
            assert isinstance(tc["steps"], list)
            assert "expected_result" in tc


# ══════════════════════════════════════════════════════════
# 真实 API 集成测试
# ══════════════════════════════════════════════════════════

@pytest.mark.integration
class TestTestCaseServiceWithRealAPI:
    """真实 DeepSeek API 集成测试。

    运行方式:
        pytest tests/test_services/test_testcase_service.py -v -m integration
    """

    def test_generate_login_cases(self, sample_test_points: list) -> None:
        """真实 API：为「用户登录」测试点生成测试用例。"""
        service = TestCaseService()
        cases = service.generate("用户登录", sample_test_points)

        # ── 基础校验 ──────────────────────────────
        assert len(cases) >= 4  # 至少每个维度 1 条
        for tc in cases:
            assert isinstance(tc, TestCaseItem)

        # ── 结构完整性 ────────────────────────────
        ids = [tc.id for tc in cases]
        # ID 格式检查
        for id_ in ids:
            assert id_.startswith("TC-"), f"ID 格式错误: {id_}"

        # ── 内容质量 ──────────────────────────────
        for tc in cases:
            # steps 必须有具体数据
            assert len(tc.steps) >= 2, f"{tc.id}: steps 不足"
            # 每步应包含动词或具体操作
            steps_text = " ".join(tc.steps)
            assert any(
                word in steps_text
                for word in ("输入", "点击", "打开", "验证", "选择", "检查")
            ), f"{tc.id}: 步骤缺少操作动词: {steps_text[:100]}"
            # expected_result 不可笼统
            assert len(tc.expected_result) >= 5
            assert tc.expected_result not in ("成功", "失败", "正常", "通过")

    def test_generate_to_dict_format(self) -> None:
        """真实 API：generate_to_dict 输出标准格式。"""
        service = TestCaseService()
        result = service.generate_to_dict("密码修改", [
            {"category": "功能测试", "description": "正常修改密码"},
            {"category": "异常测试", "description": "原密码错误"},
            {"category": "安全测试", "description": "越权修改他人密码"},
            {"category": "边界值测试", "description": "新密码输入1个字符"},
        ])

        assert isinstance(result, list)
        assert len(result) >= 4
        for tc in result:
            assert set(tc.keys()) == {
                "id", "title", "precondition", "steps", "expected_result",
            }
            assert len(tc["steps"]) >= 2
            assert len(tc["expected_result"]) >= 5

    def test_generate_cases_structure_stable(self) -> None:
        """真实 API：验证输出结构稳定性 — 连续两次输出结构一致。"""
        service = TestCaseService()
        points = [
            {"category": "功能测试", "description": "正确账号密码登录"},
        ]

        result1 = service.generate_to_dict("登录", points)
        result2 = service.generate_to_dict("登录", points)

        # 两次输出的顶层结构稳定，但数量可能因 LLM 策略选择而波动
        assert result1
        assert result2
        for tc in result1 + result2:
            assert set(tc.keys()) == {
                "id", "title", "precondition", "steps", "expected_result",
            }
            assert isinstance(tc["steps"], list)
            assert len(tc["steps"]) >= 2
