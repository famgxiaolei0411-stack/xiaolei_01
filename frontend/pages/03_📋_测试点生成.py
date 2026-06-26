"""
测试点生成页面 — AI 生成 + 人工编辑
=====================================
"""

import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


import streamlit as st
import pandas as pd

from frontend.utils.api_client import (
    generate_testpoints,
    list_testpoints,
    list_features,
    add_testpoint,
    update_testpoint,
    remove_testpoint,
)
from frontend.utils.constants import APP_TITLE, PRIORITY_OPTIONS, TEST_CATEGORIES
from frontend.utils.session import init_session
from frontend.components.sidebar import render_sidebar

st.set_page_config(
    page_title=f"测试点生成 - {APP_TITLE}",
    page_icon="📋",
    layout="wide",
)

init_session()

# ── 检查项目 ──────────────────────────────────────
project_id = st.session_state.get("project_id")
if not project_id:
    st.warning("⚠️ 请先在「上传文档」页面选择或创建项目")
    st.stop()

# ── 自动刷新功能点状态 ────────────────────────────
try:
    f_result = list_features(project_id)
    features = f_result.get("data", {}).get("features", [])
    if features:
        st.session_state["project_status"] = "features_extracted"
except Exception as exc:
    st.warning(f"⚠️ 加载功能点失败: {exc}")
    features = []

try:
    tp_result_for_status = list_testpoints(project_id)
    existing_testpoints_for_status = tp_result_for_status.get("data", {}).get("testpoints", [])
    if existing_testpoints_for_status and st.session_state.get("project_status", "") not in ("generating_testpoints", "generating_testcases", "testcases_generated", "exporting", "exported"):
        st.session_state["project_status"] = "testpoints_generated"
except Exception:
    pass

render_sidebar()
st.title("📋 测试点生成与管理")

def _do_generate_tp(pid: int) -> None:
    """后台线程：调用 API 生成测试点。"""
    try:
        result = generate_testpoints(pid)
        st.session_state["tp_gen_result"] = result
    except Exception as exc:
        st.session_state["tp_gen_error"] = str(exc)
    st.session_state["generating_testpoints"] = False


def render_generate_section() -> None:
    """渲染 AI 生成测试点区域。"""
    st.subheader("🤖 AI 生成测试点")

    generating = st.session_state.get("generating_testpoints", False)

    col1, col2 = st.columns([2, 1])
    with col1:
        if generating:
            st.info("⏳ 测试点正在后台生成中...（可切换页面，生成不会中断）")
            if "tp_gen_result" in st.session_state:
                result = st.session_state.pop("tp_gen_result")
                st.success(result.get("message", "生成完成"))
                data = result.get("data", {})
                st.info(f"共生成 {data.get('count', 0)} 个测试点")
                st.session_state["project_status"] = "testpoints_generated"
                st.session_state.pop("generating_testpoints", None)
                import time as _t; _t.sleep(1); st.rerun()
            elif "tp_gen_error" in st.session_state:
                err = st.session_state.pop("tp_gen_error")
                st.error(f"生成失败: {err}")
                st.session_state.pop("generating_testpoints", None)
                st.rerun()
            else:
                import time as _t; _t.sleep(3); st.rerun()
        elif st.button("📋 开始生成测试点", type="primary", use_container_width=True):
            st.session_state["generating_testpoints"] = True
            threading.Thread(target=_do_generate_tp, args=(project_id,), daemon=True).start()
            st.rerun()

    with col2:
        st.caption("测试点覆盖维度：")
        st.caption("✅ 功能测试（正向+逆向+边界）")
        st.caption("✅ 业务规则校验")
        st.caption("✅ 异常场景处理")
        st.caption("✅ 数据边界与特殊字符")
        st.caption("✅ 安全与性能场景")


def load_testpoints() -> list[dict] | None:
    """从后端加载测试点列表。"""
    try:
        result = list_testpoints(project_id)
        return result.get("data", {}).get("testpoints", [])
    except Exception as exc:
        st.error(f"加载测试点失败: {exc}")
        return None


def render_testpoints_list() -> None:
    """渲染测试点列表和编辑功能。"""
    st.markdown("---")
    st.subheader("📊 测试点列表")

    testpoints = load_testpoints()

    if testpoints is None:
        st.stop()

    if not testpoints:
        st.info("📭 暂无测试点 — 请先完成「功能点提取」，然后点击上方「开始生成测试点」按钮")
        return

    st.caption(f"共 {len(testpoints)} 个测试点 | 支持新增、修改、删除")

    # ── 统计信息 ──────────────────────────────────
    categories = {}
    for tp in testpoints:
        cat = tp.get("category", "其他")
        categories[cat] = categories.get(cat, 0) + 1

    cols = st.columns(len(categories) if categories else 1)
    for i, (cat, count) in enumerate(categories.items()):
        cols[i].metric(cat, f"{count} 个")

    # ── 数据表格 ──────────────────────────────────
    df_data = []
    for tp in testpoints:
        df_data.append({
            "关联功能点": tp.get("feature_name", ""),
            "类型": tp.get("category", ""),
            "描述": tp.get("description", ""),
            "预期结果": tp.get("expected_result", ""),
            "测试数据": tp.get("test_data", "-"),
            "优先级": tp.get("priority", ""),
        })
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True, hide_index=True, height=300)

    # ── 编辑/删除 ────────────────────────────────
    st.markdown("---")
    st.subheader("✏️ 编辑/删除测试点")

    tp_ids = [tp["id"] for tp in testpoints]
    selected_id = st.selectbox(
        "选择测试点",
        tp_ids,
        format_func=lambda x: next(
            (f"[{tp.get('category', '')}] {tp.get('description', '')[:60]}" for tp in testpoints if tp["id"] == x),
            str(x),
        ),
        key="tp_select",
    )

    if selected_id:
        selected = next((tp for tp in testpoints if tp["id"] == selected_id), None)
        if selected:
            with st.form("edit_tp_form"):
                col1, col2 = st.columns(2)
                with col1:
                    new_feature_name = st.text_input(
                        "关联功能点", value=selected.get("feature_name", "")
                    )
                    new_category = st.selectbox(
                        "测试类型",
                        TEST_CATEGORIES,
                        index=TEST_CATEGORIES.index(selected.get("category", "功能测试"))
                        if selected.get("category", "") in TEST_CATEGORIES
                        else 0,
                    )
                    new_priority = st.selectbox(
                        "优先级",
                        PRIORITY_OPTIONS,
                        index=PRIORITY_OPTIONS.index(selected.get("priority", "P1"))
                        if selected.get("priority", "") in PRIORITY_OPTIONS
                        else 1,
                    )
                with col2:
                    new_desc = st.text_area(
                        "测试点描述", value=selected.get("description", ""), height=120
                    )
                    new_expected = st.text_area(
                        "预期结果", value=selected.get("expected_result", ""), height=120
                    )
                new_test_data = st.text_input(
                    "建议测试数据", value=selected.get("test_data", "")
                )

                col_btn1, col_btn2, _ = st.columns([1, 1, 4])
                with col_btn1:
                    if st.form_submit_button("💾 保存修改", type="primary"):
                        try:
                            update_testpoint(project_id, selected_id, {
                                "feature_name": new_feature_name,
                                "category": new_category,
                                "description": new_desc,
                                "expected_result": new_expected,
                                "test_data": new_test_data,
                                "priority": new_priority,
                            })
                            st.success("测试点已更新")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"更新失败: {exc}")
                with col_btn2:
                    if st.form_submit_button("🗑️ 删除此测试点"):
                        try:
                            remove_testpoint(project_id, selected_id)
                            st.success("测试点已删除")
                            st.rerun()
                        except Exception as exc:
                            st.error(f"删除失败: {exc}")

    # ── 新增测试点 ────────────────────────────────
    st.markdown("---")
    st.subheader("➕ 新增测试点")
    with st.expander("点击展开新增表单"):
        with st.form("add_tp_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_feature_name = st.text_input("关联功能点名称", key="ntp_feature")
                new_category = st.selectbox("测试类型", TEST_CATEGORIES, key="ntp_cat")
                new_priority = st.selectbox("优先级", PRIORITY_OPTIONS, key="ntp_pri")
            with col2:
                new_desc = st.text_area("测试点描述", key="ntp_desc", height=120)
                new_expected = st.text_area("预期结果", key="ntp_exp", height=120)
            new_test_data = st.text_input("建议测试数据", key="ntp_data")

            if st.form_submit_button("✅ 添加测试点", type="primary"):
                if not new_desc.strip():
                    st.error("测试点描述不能为空")
                else:
                    try:
                        add_testpoint(project_id, {
                            "feature_name": new_feature_name,
                            "category": new_category,
                            "description": new_desc,
                            "expected_result": new_expected,
                            "test_data": new_test_data,
                            "priority": new_priority,
                        })
                        st.success("测试点已添加")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"添加失败: {exc}")


# ── 渲染 ──────────────────────────────────────────
render_generate_section()
render_testpoints_list()

from frontend.utils.localize import inject_localize
inject_localize()
