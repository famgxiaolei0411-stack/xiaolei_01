"""
测试用例生成页面 — AI 生成 + 人工编辑
=======================================
"""

import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


import streamlit as st
import pandas as pd

from frontend.utils.api_client import (
    generate_testcases,
    list_testcases,
    list_testpoints,
    add_testcase,
    update_testcase,
    remove_testcase,
)
from frontend.utils.constants import APP_TITLE, PRIORITY_OPTIONS, CASE_TYPES
from frontend.utils.session import init_session
from frontend.components.sidebar import render_sidebar

st.set_page_config(
    page_title=f"测试用例生成 - {APP_TITLE}",
    page_icon="📝",
    layout="wide",
)

init_session()
render_sidebar()

st.title("📝 测试用例生成与管理")

# ── 检查项目 ──────────────────────────────────────
project_id = st.session_state.get("project_id")
if not project_id:
    st.warning("⚠️ 请先在「上传文档」页面选择或创建项目")
    st.stop()

# ── 自动刷新状态 ──────────────────────────────────
try:
    tp_result = list_testpoints(project_id)
    tps = tp_result.get("data", {}).get("testpoints", [])
    if tps:
        st.session_state["project_status"] = "testpoints_generated"
except Exception as exc:
    st.warning(f"⚠️ 加载测试点失败: {exc}")


def _do_generate(pid: int) -> None:
    """后台线程：调用 API 生成测试用例。"""
    try:
        result = generate_testcases(pid)
        st.session_state["gen_result"] = result
    except Exception as exc:
        st.session_state["gen_error"] = str(exc)
    st.session_state["generating_testcases"] = False


def render_generate_section() -> None:
    """渲染 AI 生成测试用例区域。"""
    st.subheader("🤖 AI 生成测试用例")

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
            st.session_state.pop("generating_testcases", None)
            st.rerun()
        elif "gen_error" in st.session_state:
            err = st.session_state.pop("gen_error")
            st.error(f"生成失败: {err}")
            st.session_state.pop("generating_testcases", None)
            st.rerun()
        else:
            import time as _time
            _time.sleep(3)
            st.rerun()

    if st.button("📝 开始生成测试用例", type="primary", use_container_width=True, disabled=generating):
        st.session_state["generating_testcases"] = True
        threading.Thread(target=_do_generate, args=(project_id,), daemon=True).start()
        st.rerun()

    st.caption("生成的测试用例包含：用例编号、标题、前置条件、测试步骤、预期结果、优先级、用例类型")


def load_testcases() -> list[dict]:
    """从后端加载测试用例列表。"""
    try:
        result = list_testcases(project_id)
        return result.get("data", {}).get("testcases", [])
    except Exception as exc:
        st.error(f"加载测试用例失败: {exc}")
        return []


def render_testcases_list() -> None:
    """渲染测试用例列表和编辑功能。"""
    st.markdown("---")
    st.subheader("📋 测试用例列表")

    testcases = load_testcases()

    if not testcases:
        st.info("📭 暂无测试用例 — 请先完成「测试点生成」，然后点击上方「开始生成测试用例」按钮")
        return

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

    st.caption(f"共 {len(testcases)} 个测试用例 | 支持修改标题、步骤、预期结果、删除")

    # ── 统计信息 ──────────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric("总用例数", len(testcases))
    forward = sum(1 for tc in testcases if tc.get("case_type") == "正向")
    reverse = sum(1 for tc in testcases if tc.get("case_type") == "逆向")
    boundary = sum(1 for tc in testcases if tc.get("case_type") == "边界")
    col2.metric("正向/逆向/边界", f"{forward}/{reverse}/{boundary}")
    p0 = sum(1 for tc in testcases if tc.get("priority") == "P0")
    col3.metric("P0 高优先级", p0)

    # ── 数据表格 ──────────────────────────────────
    df_data = []
    for tc in testcases:
        steps = tc.get("steps", [])
        if isinstance(steps, list):
            steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
        else:
            steps_text = str(steps)
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
        })
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True, hide_index=True, height=300)

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

                # ── 步骤编辑 ────────────────────────
                steps_str = st.text_area(
                    "测试步骤（每行一步）",
                    value="\n".join(selected.get("steps", [])) if isinstance(selected.get("steps"), list) else str(selected.get("steps", "")),
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
                            })
                            st.success("测试用例已更新")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"更新失败: {exc}")
                with col_btn2:
                    if st.form_submit_button("🗑️ 删除此用例"):
                        try:
                            remove_testcase(project_id, selected_id)
                            st.success("测试用例已删除")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"删除失败: {exc}")

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
                        })
                        st.success("测试用例已添加")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"添加失败: {exc}")


# ── 渲染 ──────────────────────────────────────────
render_generate_section()
render_testcases_list()

from frontend.utils.localize import inject_localize
inject_localize()
