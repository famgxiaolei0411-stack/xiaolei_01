"""
测试用例生成页面 — AI 生成 + 人工编辑
=======================================
"""

import sys
import threading
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


import streamlit as st
import pandas as pd

from frontend.utils.api_client import (
    generate_testcases,
    get_document,
    list_testcases,
    get_testcase_review,
    list_testpoints,
    add_testcase,
    update_testcase,
    remove_testcase,
)
from frontend.utils.constants import APP_TITLE, PRIORITY_OPTIONS, CASE_TYPES
from frontend.utils.session import init_session
from frontend.components.sidebar import render_sidebar
from frontend.components.platform_widgets import (
    render_api_contract_metrics,
    render_quality_score_card,
    render_skill_badges,
    render_table_filters,
)
from frontend.utils.ux import show_error
from services.case_type import infer_case_type

st.set_page_config(
    page_title=f"测试用例生成 - {APP_TITLE}",
    page_icon="📝",
    layout="wide",
)

init_session()

# ── 检查项目 ──────────────────────────────────────
project_id = st.session_state.get("project_id")
if not project_id:
    st.warning("⚠️ 请先在「上传文档」页面选择或创建项目")
    st.stop()

# ── 自动刷新状态 ──────────────────────────────────
try:
    tp_result = list_testpoints(project_id)
    tps = tp_result.get("data", {}).get("testpoints", [])
    if tps and st.session_state.get("project_status", "") not in ("generating_testcases", "testcases_generated", "exporting", "exported"):
        st.session_state["project_status"] = "testpoints_generated"
except Exception as exc:
    show_error("加载数据", exc)

try:
    tc_result_for_status = list_testcases(project_id)
    existing_testcases_for_status = tc_result_for_status.get("data", {}).get("testcases", [])
    if existing_testcases_for_status and st.session_state.get("project_status", "") not in ("generating_testcases", "exporting", "exported"):
        st.session_state["project_status"] = "testcases_generated"
except Exception:
    pass

render_sidebar()
st.title("📝 测试用例生成与管理")

def _do_generate(pid: int, mode: str) -> None:
    """后台线程：调用 API 生成测试用例。"""
    try:
        result = generate_testcases(pid, mode)
        st.session_state["gen_result"] = result
    except Exception as exc:
        st.session_state["gen_error"] = str(exc)
    st.session_state["generating_testcases"] = False


def render_generate_section() -> None:
    """渲染 AI 生成测试用例区域。"""
    st.subheader("🤖 AI 生成测试用例")

    mode = "auto"
    detected_mode = "functional"
    try:
        doc_result = get_document(project_id)
        doc_data = doc_result.get("data", {})
        detected_mode = doc_data.get("testcase_mode", "functional")
        st.info(
            f"系统已自动识别为：{doc_data.get('doc_type', '需求文档')}，"
            f"将按{'接口测试 (method/URL/Body)' if detected_mode == 'api' else '功能测试 (步骤/预期)'}生成"
        )
    except Exception:
        st.caption("系统会根据已上传文档自动选择接口测试或功能测试生成方式")

    mode_options = {
        "auto": "自动识别",
        "api": "接口测试",
        "functional": "功能测试",
    }
    mode = st.radio(
        "生成模式",
        options=list(mode_options.keys()),
        format_func=lambda key: mode_options[key],
        index=0,
        horizontal=True,
        help="自动识别不准时，可以手动指定生成接口测试或功能测试用例。",
    )
    if mode == "auto":
        st.caption(
            f"当前自动识别结果：{'接口测试' if detected_mode == 'api' else '功能测试'}"
        )

    generating = st.session_state.get("generating_testcases", False)

    if generating:
        st.info("⏳ 测试用例正在后台生成中...（可切换页面，生成不会中断）")
        # 检查后台线程是否完成
        if "gen_result" in st.session_state:
            result = st.session_state.pop("gen_result")
            data = result.get("data", {})
            review = data.get("review", {})

            # 简短摘要
            score = review.get("score", 0)
            icon = "✅" if score >= 60 else "⚠️"
            st.success(f"{icon} {result.get('message', '生成完成')} | 评审 {score} 分")

            # 将问题注入到 session，在列表展示时标记
            st.session_state["case_issues"] = review.get("issues", [])
            st.session_state["review_summary"] = review.get("summary", "")
            st.session_state["project_status"] = "testcases_generated"
            st.session_state["doc_type"] = data.get("doc_type", "")
            st.session_state["testcase_mode"] = data.get("testcase_mode", "")
            st.session_state.pop("generating_testcases", None)
            st.rerun()
        elif "gen_error" in st.session_state:
            err = st.session_state.pop("gen_error")
            show_error("测试用例生成", Exception(err))
            st.session_state.pop("generating_testcases", None)
            st.rerun()
        else:
            import time as _time
            _time.sleep(3)
            st.rerun()

    if st.button("📝 开始生成测试用例", type="primary", use_container_width=True, disabled=generating):
        st.session_state["generating_testcases"] = True
        st.session_state["project_status"] = "generating_testcases"
        threading.Thread(target=_do_generate, args=(project_id, mode), daemon=True).start()
        st.rerun()

    st.caption("接口模式会生成 Method、URL、Header、Body；功能模式会生成步骤、测试数据、预期结果。")



def normalize_case_type(tc: dict) -> str:
    """统一页面上的用例类型展示，兼容历史误分类数据。"""
    return infer_case_type(
        tc.get("title", ""),
        expected=tc.get("expected", ""),
        steps=tc.get("steps", []),
        current=tc.get("case_type", "正向"),
    )


def steps_to_lines(steps: list | str | None) -> list[str]:
    """把历史单行编号步骤整理成逐行步骤。"""
    if isinstance(steps, list):
        raw_lines = [str(step).strip() for step in steps if str(step).strip()]
    else:
        raw_lines = [str(steps or "").strip()] if steps else []

    if len(raw_lines) == 1:
        parts = re.split(r"\s*(?=\d+[.、]\s*)", raw_lines[0])
        split_lines = [part.strip() for part in parts if part.strip()]
        if len(split_lines) > 1:
            raw_lines = split_lines
    return [re.sub(r"^\d+[.、]\s*", "", line).strip() for line in raw_lines]
def load_testcases() -> list[dict] | None:
    """从后端加载测试用例列表。"""
    try:
        result = list_testcases(project_id)
        testcases = result.get("data", {}).get("testcases", [])
        for tc in testcases:
            tc["case_type"] = normalize_case_type(tc)
        return testcases
    except Exception as exc:
        show_error("加载数据", exc)
        return None


def get_current_testcase_mode(testcases: list[dict] | None = None) -> str:
    """获取当前项目的用例模式。"""
    if testcases and any(tc.get(field) for tc in testcases for field in ("method", "url", "headers", "body")):
        return "api"
    try:
        doc_result = get_document(project_id)
        return doc_result.get("data", {}).get("testcase_mode", "functional")
    except Exception:
        return st.session_state.get("testcase_mode", "functional") or "functional"


def render_testcases_list() -> None:
    """渲染测试用例列表和编辑功能。"""
    st.markdown("---")
    st.subheader("📋 测试用例列表")

    testcases = load_testcases()

    if testcases is None:
        st.stop()

    if not testcases:
        st.info("📭 暂无测试用例 — 请先完成「测试点生成」，然后点击上方「开始生成测试用例」按钮")
        return

    if st.session_state.get("project_status", "") not in ("exporting", "exported"):
        st.session_state["project_status"] = "testcases_generated"

    current_mode = get_current_testcase_mode(testcases)
    enabled_skills = ["边界值分析", "等价类划分"]
    if current_mode == "api" or any(tc.get(field) for tc in testcases for field in ("method", "url", "headers", "body")):
        enabled_skills.append("接口契约检查")
    render_skill_badges(enabled_skills, title="测试用例与评审已启用 Skill")

    # ── 评审问题标记 ──────────────────────────────
    issues = st.session_state.get("case_issues", []) or []
    issue_map: dict[str, list] = {}
    for iss in issues:
        cid = iss.get("case_id", "")
        issue_map.setdefault(cid, []).append(iss)

    summary = st.session_state.get("review_summary", "")
    if summary or issues:
        err_count = sum(1 for i in issues if i.get("level") == "error")
        warn_count = sum(1 for i in issues if i.get("level") == "warning")
        parts = []
        if err_count: parts.append(f"🔴 {err_count} 个错误")
        if warn_count: parts.append(f"🟡 {warn_count} 个警告")
        st.warning(f"📋 {summary}  {' | '.join(parts)}" if parts else f"📋 {summary}")
        if st.button("✕ 清除评审标记", key="clear_review"):
            st.session_state["case_issues"] = []
            st.session_state["review_summary"] = ""
            st.rerun()

    st.caption(
        f"共 {len(testcases)} 个测试用例 | "
        f"当前模板：{'接口测试' if current_mode == 'api' else '功能测试'} | "
        "支持修改标题、步骤、预期结果、删除"
    )

    # ── 统计信息 ──────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总用例数", len(testcases))
    forward = sum(1 for tc in testcases if tc.get("case_type") == "正向")
    reverse = sum(1 for tc in testcases if tc.get("case_type") == "逆向")
    boundary = sum(1 for tc in testcases if tc.get("case_type") == "边界")
    col2.metric("正向/逆向/边界", f"{forward}/{reverse}/{boundary}")
    p0 = sum(1 for tc in testcases if tc.get("priority") == "P0")
    col3.metric("P0 高优先级", p0)
    issue_case_ids = {item.get("case_id") for item in issues if item.get("case_id")}
    col4.metric("有评审问题", len(issue_case_ids))

    try:
        review_result = get_testcase_review(project_id)
        review = review_result.get("data", {}) or {}
        metrics = review.get("metrics", {}) or {}
        render_quality_score_card(review)
        render_api_contract_metrics(metrics)
    except Exception as exc:
        st.caption("质量评审暂不可用，用例列表仍可继续查看和编辑。")
        with st.expander("查看质量评审加载细节"):
            st.code(str(exc))

    # ── 数据表格 ──────────────────────────────────
    df_data = []
    for tc in testcases:
        steps = tc.get("steps", [])
        step_lines = steps_to_lines(steps)
        steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(step_lines))
        # 评审标记
        cid = tc.get("case_id", "")
        flags = issue_map.get(cid, [])
        flag_text = ""
        if flags:
            levels = {i.get("level") for i in flags}
            if "error" in levels: flag_text = "🔴"
            elif "warning" in levels: flag_text = "🟡"
            else: flag_text = "🔵"

        df_data.append({
            "": flag_text,
            "编号": cid,
            "标题": tc.get("title", ""),
            "前置条件": tc.get("precondition", ""),
            "步骤": steps_text[:100] + ("..." if len(steps_text) > 100 else ""),
            "预期": tc.get("expected", ""),
            "优先级": tc.get("priority", ""),
            "类型": tc.get("case_type", ""),
            "接口方法": tc.get("method", ""),
            "问题": "有问题" if flags else "无问题",
        })
    df = pd.DataFrame(df_data)
    filter_columns = ["优先级", "类型", "问题"]
    if current_mode == "api":
        filter_columns.append("接口方法")
    filtered_df = render_table_filters(
        df,
        key_prefix="tc_table",
        search_columns=["编号", "标题", "步骤", "预期"],
        filter_columns=filter_columns,
    )
    st.dataframe(filtered_df, use_container_width=True, hide_index=True, height=300)

    # ── 编辑/删除 ────────────────────────────────
    st.markdown("---")
    st.subheader("✏️ 编辑/删除测试用例")

    tc_ids = [tc["id"] for tc in testcases]
    selected_id = st.selectbox(
        "选择测试用例",
        tc_ids,
        format_func=lambda x: next(
            (f"{'🔴' if issue_map.get(tc.get('case_id','')) else ''}"
             f"[{tc.get('case_id', '')}] {tc.get('title', '')[:80]}"
             for tc in testcases if tc["id"] == x),
            str(x),
        ),
        key="tc_select",
    )

    if selected_id:
        selected = next((tc for tc in testcases if tc["id"] == selected_id), None)
        if selected:
            is_api_case = any(selected.get(field) for field in ("method", "url", "headers", "body"))
            with st.form("edit_tc_form"):
                col1, col2 = st.columns(2)
                with col1:
                    new_case_id = st.text_input(
                        "用例编号", value=selected.get("case_id", "")
                    )
                    new_title = st.text_input(
                        "用例标题", value=selected.get("title", "")
                    )
                    new_priority = st.selectbox(
                        "优先级",
                        PRIORITY_OPTIONS,
                        index=PRIORITY_OPTIONS.index(selected.get("priority", "P1"))
                        if selected.get("priority", "") in PRIORITY_OPTIONS
                        else 1,
                    )
                    new_case_type = st.selectbox(
                        "用例类型",
                        CASE_TYPES,
                        index=CASE_TYPES.index(selected.get("case_type", "正向"))
                        if selected.get("case_type", "") in CASE_TYPES
                        else 0,
                    )
                with col2:
                    new_precondition = st.text_area(
                        "前置条件", value=selected.get("precondition", ""), height=120
                    )
                    new_expected = st.text_area(
                        "预期结果", value=selected.get("expected", ""), height=120
                    )

                new_method = selected.get("method", "")
                new_url = selected.get("url", "")
                new_headers = selected.get("headers", "")
                new_body = selected.get("body", "")
                if is_api_case:
                    st.markdown("#### 接口字段")
                    api_col1, api_col2 = st.columns([1, 3])
                    with api_col1:
                        new_method = st.text_input("请求方法", value=new_method)
                    with api_col2:
                        new_url = st.text_input("URL", value=new_url)
                    new_headers = st.text_area("请求头", value=new_headers, height=90)
                    new_body = st.text_area("请求体", value=new_body, height=120)

                # ── 步骤编辑 ────────────────────────
                step_lines = steps_to_lines(selected.get("steps", []))
                steps_str = st.text_area(
                    "测试步骤（每行一步）",
                    value="\n".join(step_lines),
                    height=150,
                    help="每行一个步骤",
                )

                col_btn1, col_btn2, _ = st.columns([1, 1, 4])
                with col_btn1:
                    if st.form_submit_button("💾 保存修改", type="primary"):
                        try:
                            update_testcase(project_id, selected_id, {
                                "case_id": new_case_id,
                                "title": new_title,
                                "precondition": new_precondition,
                                "steps": [
                                    line.strip()
                                    for line in steps_str.split("\n")
                                    if line.strip()
                                ],
                                "expected": new_expected,
                                "priority": new_priority,
                                "case_type": new_case_type,
                                "method": new_method,
                                "url": new_url,
                                "headers": new_headers,
                                "body": new_body,
                            })
                            st.success("测试用例已更新")
                            st.rerun()
                        except Exception as exc:
                            show_error("更新", exc)
                with col_btn2:
                    if st.form_submit_button("🗑️ 删除此用例"):
                        try:
                            remove_testcase(project_id, selected_id)
                            st.success("测试用例已删除")
                            st.rerun()
                        except Exception as exc:
                            show_error("删除", exc)

    # ── 新增测试用例 ──────────────────────────────
    st.markdown("---")
    st.subheader("➕ 新增测试用例")
    with st.expander("点击展开新增表单"):
        with st.form("add_tc_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_case_id = st.text_input("用例编号", key="ntc_cid", placeholder="如 TC-LOGIN-001")
                new_title = st.text_input("用例标题", key="ntc_title")
                new_priority = st.selectbox("优先级", PRIORITY_OPTIONS, key="ntc_pri")
                new_case_type = st.selectbox("用例类型", CASE_TYPES, key="ntc_type")
            with col2:
                new_precondition = st.text_area("前置条件", key="ntc_pre", height=100)
                new_expected = st.text_area("预期结果", key="ntc_exp", height=100)
            new_method = ""
            new_url = ""
            new_headers = ""
            new_body = ""
            if current_mode == "api":
                st.markdown("#### 接口字段")
                api_col1, api_col2 = st.columns([1, 3])
                with api_col1:
                    new_method = st.text_input("请求方法", key="ntc_method", placeholder="GET")
                with api_col2:
                    new_url = st.text_input("URL", key="ntc_url", placeholder="/api/example")
                new_headers = st.text_area("请求头", key="ntc_headers", height=80, placeholder='{"Authorization": "Bearer token"}')
                new_body = st.text_area("请求体", key="ntc_body", height=100, placeholder="无请求体或 JSON")
            new_steps = st.text_area("测试步骤（每行一步）", key="ntc_steps", height=120)
            new_tp_desc = st.text_input("关联测试点描述（可选）", key="ntc_tp")

            if st.form_submit_button("✅ 添加测试用例", type="primary"):
                if not new_title.strip():
                    st.error("用例标题不能为空")
                else:
                    try:
                        add_testcase(project_id, {
                            "testpoint_description": new_tp_desc,
                            "case_id": new_case_id,
                            "title": new_title,
                            "precondition": new_precondition,
                            "steps": [
                                line.strip()
                                for line in new_steps.split("\n")
                                if line.strip()
                            ],
                            "expected": new_expected,
                            "priority": new_priority,
                            "case_type": new_case_type,
                            "method": new_method,
                            "url": new_url,
                            "headers": new_headers,
                            "body": new_body,
                        })
                        st.success("测试用例已添加")
                        st.rerun()
                    except Exception as exc:
                        show_error("添加", exc)


# ── 渲染 ──────────────────────────────────────────
render_generate_section()
render_testcases_list()

from frontend.utils.localize import inject_localize
inject_localize()
