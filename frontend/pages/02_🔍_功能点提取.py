"""
功能点提取页面 — AI 提取 + 人工编辑
=====================================
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import pandas as pd

from frontend.utils.api_client import (
    extract_features,
    list_features,
    add_feature,
    update_feature,
    remove_feature,
)
from frontend.utils.constants import APP_TITLE, PRIORITY_OPTIONS
from frontend.utils.session import init_session
from frontend.components.sidebar import render_sidebar

st.set_page_config(
    page_title=f"功能点提取 - {APP_TITLE}",
    page_icon="🔍",
    layout="wide",
)

init_session()
render_sidebar()

st.title("🔍 功能点提取与管理")

# ── 检查项目是否已选择 ────────────────────────────
project_id = st.session_state.get("project_id")
if not project_id:
    st.warning("⚠️ 请先在「上传文档」页面选择或创建项目")
    st.stop()


# ══════════════════════════════════════════════════════════
# AI 提取功能点
# ══════════════════════════════════════════════════════════

def render_extract_section() -> None:
    """渲染 AI 提取功能点区域。"""
    st.subheader("🤖 AI 提取功能点")

    col1, col2 = st.columns([2, 1])
    with col1:
        if st.button("🔍 开始提取功能点", type="primary", use_container_width=True):
            with st.spinner("AI 正在分析文档并提取功能点..."):
                try:
                    result = extract_features(project_id)
                    st.success(result.get("message", "提取完成"))
                    data = result.get("data", {})
                    st.info(f"共提取 {data.get('count', 0)} 个功能点")
                    st.session_state["project_status"] = "features_extracted"
                    # 刷新功能点列表
                    st.session_state["_features_cache"] = None
                    st.rerun()
                except Exception as exc:
                    st.error(f"提取失败: {exc}")

    with col2:
        st.caption("AI 将自动：")
        st.caption("1. 分析文档内容和结构")
        st.caption("2. 识别功能模块和功能点")
        st.caption("3. 判定优先级和前置条件")
        st.caption("4. 自动去重并排序输出")


# ══════════════════════════════════════════════════════════
# 功能点列表与编辑
# ══════════════════════════════════════════════════════════

def load_features() -> list[dict]:
    """从后端加载功能点列表。"""
    try:
        result = list_features(project_id)
        return result.get("data", {}).get("features", [])
    except Exception as exc:
        st.error(f"加载功能点失败: {exc}")
        return []


def render_features_list() -> None:
    """渲染功能点列表和编辑功能。"""
    st.markdown("---")
    st.subheader("📋 功能点列表")

    features = load_features()

    if not features:
        st.info("📭 暂无功能点 — 请先上传需求文档，然后点击上方「🚀 开始提取功能点」按钮")
        return

    st.caption(f"共 {len(features)} 个功能点 | 支持新增、修改、删除")

    # ── 显示功能点表格 ────────────────────────────
    df_data = []
    for f in features:
        df_data.append({
            "ID": f["id"],
            "模块": f["module"],
            "功能点": f["name"],
            "描述": f["description"][:80] + ("..." if len(f.get("description", "")) > 80 else ""),
            "优先级": f["priority"],
            "前置条件": "\n".join(f.get("preconditions", [])) or "-",
        })

    if df_data:
        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True, hide_index=True, height=300)

        # ── 选中功能点查看/编辑详情 ────────────────
        st.markdown("---")
        st.subheader("✏️ 编辑/删除功能点")

        feature_ids = [f["id"] for f in features]
        selected_id = st.selectbox(
            "选择功能点",
            feature_ids,
            format_func=lambda x: next(
                (f"{f['module']} / {f['name']}" for f in features if f["id"] == x),
                str(x),
            ),
            key="feature_select",
        )

        if selected_id:
            selected = next((f for f in features if f["id"] == selected_id), None)
            if selected:
                # ── 编辑表单 ────────────────────────
                with st.form("edit_feature_form"):
                    col1, col2 = st.columns(2)
                    with col1:
                        new_module = st.text_input(
                            "所属模块", value=selected["module"]
                        )
                        new_name = st.text_input(
                            "功能点名称", value=selected["name"]
                        )
                        new_priority = st.selectbox(
                            "优先级",
                            PRIORITY_OPTIONS,
                            index=PRIORITY_OPTIONS.index(selected["priority"])
                            if selected["priority"] in PRIORITY_OPTIONS
                            else 2,
                        )
                    with col2:
                        new_description = st.text_area(
                            "功能描述", value=selected.get("description", ""), height=150
                        )
                        new_preconditions = st.text_area(
                            "前置条件（每行一条）",
                            value="\n".join(selected.get("preconditions", [])),
                            height=100,
                        )

                    col_btn1, col_btn2, _ = st.columns([1, 1, 4])
                    with col_btn1:
                        submitted = st.form_submit_button("💾 保存修改", type="primary")
                        if submitted:
                            updates = {
                                "module": new_module,
                                "name": new_name,
                                "description": new_description,
                                "priority": new_priority,
                                "preconditions": [
                                    line.strip()
                                    for line in new_preconditions.split("\n")
                                    if line.strip()
                                ],
                            }
                            try:
                                update_feature(project_id, selected_id, updates)
                                st.success("功能点已更新")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"更新失败: {exc}")
                    with col_btn2:
                        if st.form_submit_button("🗑️ 删除此功能点"):
                            try:
                                remove_feature(project_id, selected_id)
                                st.success("功能点已删除")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"删除失败: {exc}")

    # ── 新增功能点 ────────────────────────────────
    st.markdown("---")
    st.subheader("➕ 新增功能点")

    with st.expander("点击展开新增表单"):
        with st.form("add_feature_form"):
            col1, col2 = st.columns(2)
            with col1:
                new_module = st.text_input("所属模块", key="new_f_module")
                new_name = st.text_input("功能点名称", key="new_f_name")
                new_priority = st.selectbox("优先级", PRIORITY_OPTIONS, key="new_f_priority")
            with col2:
                new_description = st.text_area("功能描述", key="new_f_desc", height=150)
                new_preconditions = st.text_area(
                    "前置条件（每行一条）", key="new_f_pre", height=100
                )

            if st.form_submit_button("✅ 添加功能点", type="primary"):
                if not new_name.strip():
                    st.error("功能点名称不能为空")
                else:
                    try:
                        add_feature(project_id, {
                            "module": new_module or "未分类",
                            "name": new_name,
                            "description": new_description,
                            "priority": new_priority,
                            "preconditions": [
                                line.strip()
                                for line in new_preconditions.split("\n")
                                if line.strip()
                            ],
                        })
                        st.success("功能点已添加")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"添加失败: {exc}")


# ══════════════════════════════════════════════════════════
# 页面渲染
# ══════════════════════════════════════════════════════════
render_extract_section()
render_features_list()

from frontend.utils.localize import inject_localize
inject_localize()
