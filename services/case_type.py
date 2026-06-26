"""Utilities for classifying generated test cases."""

from __future__ import annotations

import re
from typing import Any


VALID_CASE_TYPES = {"正向", "逆向", "边界"}
VALID_PRIORITIES = {"P0", "P1", "P2", "P3"}
PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}

BOUNDARY_PATTERN = re.compile(
    r"边界|边界值|最大|最小|极限|上限|下限|临界|超长|超短|溢出|空字符串|"
    r"长度|范围|阈值|零值|负数|小数|特殊字符|必填为空|为空"
)

NEGATIVE_PATTERN = re.compile(
    r"异常|错误|失败|无效|非法|拒绝|阻止|拦截|不存在|未授权|越权|权限不足|"
    r"超时|过期|重复|密码错误|用户名不存在|验证码失效|token失效|token过期|"
    r"SQL注入|XSS|伪造|篡改|攻击|风控",
    re.IGNORECASE,
)

POSITIVE_PATTERN = re.compile(
    r"成功|正常|正确|通过|有效|合法|保存|提交|创建|查询|获取|展示|跳转|显示|返回"
)

P0_PATTERN = re.compile(
    r"核心|主流程|登录|注册|认证|授权|权限|越权|未授权|支付|付款|扣款|充值|提现|退款|"
    r"订单提交|下单|结算|资金|金额|账务|数据丢失|删除|不可恢复|安全|SQL注入|XSS|攻击|"
    r"密码|token|生产|发布|审批通过",
    re.IGNORECASE,
)

P1_PATTERN = re.compile(
    r"提交|保存|创建|新增|编辑|修改|查询|搜索|列表|详情|上传|下载|导出|导入|审核|通知|同步|"
    r"正常|成功|主要|重要"
)

P3_PATTERN = re.compile(r"提示文案|帮助|说明|展示样式|排序|筛选|非核心|可选|锦上添花")


def _joined_text(title: str = "", expected: str = "", steps: Any = None) -> str:
    if isinstance(steps, list):
        steps_text = " ".join(str(step) for step in steps)
    else:
        steps_text = str(steps or "")
    return " ".join([str(title or ""), steps_text, str(expected or "")])


def _best_priority(priorities: set[str]) -> str | None:
    valid = priorities & VALID_PRIORITIES
    if not valid:
        return None
    return min(valid, key=lambda value: PRIORITY_ORDER[value])


def infer_case_type(
    title: str = "",
    *,
    expected: str = "",
    steps: Any = None,
    categories: set[str] | list[str] | tuple[str, ...] | None = None,
    current: str | None = None,
) -> str:
    """Infer 正向/逆向/边界 from case content, using categories as fallback.

    LLM output can be generated from merged test-point batches, so category-only
    classification may mark a whole batch as 逆向. Content wins here.
    """
    text = _joined_text(title, expected, steps)
    source_categories = set(categories or [])

    if BOUNDARY_PATTERN.search(text):
        return "边界"
    if NEGATIVE_PATTERN.search(text):
        return "逆向"
    if POSITIVE_PATTERN.search(text):
        return "正向"

    if source_categories == {"边界值测试"}:
        return "边界"
    if source_categories <= {"异常测试", "安全测试"} and source_categories:
        return "逆向"
    if source_categories == {"功能测试"}:
        return "正向"

    if current in VALID_CASE_TYPES:
        return current
    return "正向"


def source_priorities_for_case(
    title: str = "",
    *,
    expected: str = "",
    steps: Any = None,
    testpoints: list[dict] | None = None,
) -> set[str]:
    """Find likely source test-point priorities for one generated case."""
    points = testpoints or []
    text = _joined_text(title, expected, steps)
    matched: set[str] = set()
    for tp in points:
        desc = str(tp.get("description", "") or "").strip()
        test_data = str(tp.get("test_data", "") or "").strip()
        candidates = [desc[:16], desc[:10], test_data[:12]]
        if any(candidate and candidate in text for candidate in candidates):
            matched.add(str(tp.get("priority", "P1")).upper())
    if matched:
        return matched
    return {str(tp.get("priority", "P1")).upper() for tp in points}
def infer_case_priority(
    title: str = "",
    *,
    expected: str = "",
    steps: Any = None,
    source_priorities: set[str] | list[str] | tuple[str, ...] | None = None,
    case_type: str | None = None,
    current: str | None = None,
) -> str:
    """Infer P0/P1/P2/P3 for a generated case.

    Content decides first, then source test-point priority, then existing value.
    This avoids saving every generated case as P1 while still preserving obvious
    low-risk and manually edited non-P1 values.
    """
    text = _joined_text(title, expected, steps)
    priorities = {str(priority).upper() for priority in (source_priorities or [])}

    if P0_PATTERN.search(text):
        return "P0"
    if P3_PATTERN.search(text):
        return "P3"

    best_source = _best_priority(priorities)
    if best_source:
        if best_source == "P0":
            return "P0"
        if best_source in {"P2", "P3"} and case_type in {"边界", "逆向"}:
            return best_source

    if case_type == "边界":
        return "P2"
    if case_type == "逆向":
        return "P1"
    if P1_PATTERN.search(text):
        return "P1"

    if current in VALID_PRIORITIES and current != "P1":
        return current
    return best_source or "P1"


