from services.case_type import (
    infer_case_priority,
    infer_case_type,
    source_priorities_for_case,
)


def _priority(title: str) -> str:
    case_type = infer_case_type(title)
    return infer_case_priority(title, case_type=case_type)


def test_priority_infers_p0_for_core_auth_flow() -> None:
    assert _priority("登录接口 - 正确用户名密码 - 登录成功返回token") == "P0"


def test_priority_does_not_treat_search_keyword_as_p0() -> None:
    assert _priority("商品列表 - 输入关键字 - 查询成功") == "P1"


def test_priority_infers_boundary_as_p2() -> None:
    assert _priority("用户名输入框 - 超长字符 - 提示长度错误") == "P2"


def test_source_priorities_match_case_text_before_batch_fallback() -> None:
    testpoints = [
        {"description": "核心登录流程", "priority": "P0"},
        {"description": "普通列表查询", "priority": "P2"},
    ]
    assert source_priorities_for_case(
        "普通列表查询 - 查询成功",
        testpoints=testpoints,
    ) == {"P2"}
