"""
上传文档页面 — 创建项目、上传需求文档、一键生成
==================================================
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import time
import streamlit as st

from frontend.utils.api_client import (
    create_project,
    list_projects,
    upload_document,
    auto_generate,
    delete_project,
    get_download_url,
    batch_generate,
)
from frontend.utils.session import set_project, init_session
from frontend.components.sidebar import render_sidebar
from frontend.utils.constants import APP_TITLE
from frontend.utils.ux import show_error

st.set_page_config(
    page_title=f"上传文档 - {APP_TITLE}",
    page_icon="📄",
    layout="wide",
)

init_session()
render_sidebar()


def render_project_list() -> None:
    """渲染项目列表和项目创建区域。"""
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📂 已有项目")
        try:
            projects = list_projects()
        except Exception:
            st.warning("无法连接后端服务。请先运行 start.bat，或手动启动 uvicorn backend.main:app --host 127.0.0.1 --port 8000")
            projects = []

        if not projects:
            st.info("📭 暂无项目 — 请在右侧输入项目名称，点击「新建项目」开始")
        else:
            for proj in projects:
                proj_col1, proj_col2, proj_col3 = st.columns([3, 1, 1])
                with proj_col1:
                    st.markdown(f"**{proj['name']}**")
                    st.caption(
                        f"ID: {proj['id']} | 状态: {proj.get('status', '-')} "
                        f"| 创建: {proj.get('created_at', '-')[:19]}"
                    )
                with proj_col2:
                    if st.button("📌 选择", key=f"sel_{proj['id']}"):
                        set_project(
                            proj["id"],
                            proj["name"],
                            proj.get("status", ""),
                        )
                        st.rerun()
                with proj_col3:
                    if st.button("🗑️ 删除", key=f"del_{proj['id']}"):
                        try:
                            delete_project(proj["id"])
                            st.success(f"项目 '{proj['name']}' 已删除")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as exc:
                            show_error("项目删除", exc)

    with col2:
        st.subheader("🆕 创建新项目")
        custom_name = st.text_input(
            "项目名称（可选）",
            placeholder="留空则自动生成名称",
            key="new_project_name",
        )
        if st.button("➕ 新建项目", use_container_width=True, type="primary"):
            try:
                proj = create_project(custom_name.strip())
                set_project(proj["id"], proj["name"], proj.get("status", ""))
                st.success(f"项目 '{proj['name']}' 创建成功！")
                time.sleep(1.5)
                st.rerun()
            except Exception as exc:
                show_error("项目创建", exc)


def render_upload_section() -> None:
    """渲染文档上传区域。"""
    project_id = st.session_state.get("project_id")
    if not project_id:
        return

    st.markdown("---")
    st.subheader("📤 上传需求文档")

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "选择需求文档",
            type=["txt", "md", "docx", "pdf"],
            help="支持 .txt / .md / .docx / .pdf 格式",
            key="doc_uploader",
        )

        if uploaded_file is not None:
            if st.button("🚀 上传并解析", type="primary", use_container_width=True):
                with st.spinner("正在上传并解析文档..."):
                    try:
                        result = upload_document(
                            project_id,
                            uploaded_file.getvalue(),
                            uploaded_file.name,
                        )
                        st.success(result.get("message", "上传成功"))
                        data = result.get("data", {})
                        st.info(
                            f"📄 文件: {data.get('filename')} | "
                            f"📏 字符数: {data.get('char_count', 0):,} | "
                            f"🧩 分块数: {data.get('chunks', 0)}"
                        )
                        st.success(
                            f"已自动识别为：{data.get('doc_type', '需求文档')}，"
                            f"后续将按{'接口测试' if data.get('testcase_mode') == 'api' else '功能测试'}生成"
                        )
                        # 更新 session
                        st.session_state["project_status"] = "parsed"
                        st.session_state["doc_filename"] = data.get("filename", "")
                        st.session_state["doc_type"] = data.get("doc_type", "")
                        st.session_state["testcase_mode"] = data.get("testcase_mode", "")
                    except Exception as exc:
                        show_error("文档上传", exc)

    with col2:
        st.markdown("**📋 支持的格式**")
        st.markdown("""
        - 📝 `.txt` — 纯文本
        - 📋 `.md` — Markdown
        - 📘 `.docx` — Word 文档
        - 📕 `.pdf` — PDF 文档
        """)

        st.markdown("**⚙️ 处理能力**")
        st.markdown("""
        - 最大支持 100 页文档
        - 自动长文档分块
        - 智能文本清洗
        """)


def render_one_click_section() -> None:
    """渲染一键生成区域。"""
    project_id = st.session_state.get("project_id")
    if not project_id:
        return

    status = st.session_state.get("project_status", "")
    if status != "parsed":
        return

    st.markdown("---")
    st.subheader("⚡ 一键生成")

    st.markdown(
        "一键完成：**功能点提取 → 测试点生成 → 测试用例生成 → Excel 导出**"
    )

    if st.button("⚡ 开始一键生成", type="primary", use_container_width=True):
        # 显示真实的处理步骤（而非假进度条）
        status_placeholder = st.empty()

        try:
            status_placeholder.info("🔍 第1步：正在提取功能点...")
            result = auto_generate(project_id)

            status_placeholder.success("✅ 全流程完成！")
            data = result.get("data", {})

            st.success(f"✅ {result.get('message', '生成完成')}")
            st.balloons()

            # ── 显示结果统计 ────────────────────────
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("功能点", f"{data.get('features', 0)} 个")
            col2.metric("测试点", f"{data.get('testpoints', 0)} 个")
            col3.metric("测试用例", f"{data.get('testcases', 0)} 个")
            col4.metric("Excel 文件", data.get("excel_file", "-"))
            st.info(
                f"文档类型：{data.get('doc_type', '自动识别')} | "
                f"用例类型：{'接口测试' if data.get('testcase_mode') == 'api' else '功能测试'}"
            )

            # ── 更新状态 ────────────────────────────
            st.session_state["project_status"] = "exported"

            # ── 下载链接 ────────────────────────────
            excel_file = data.get("excel_file", "")
            if excel_file:
                from frontend.utils.constants import BACKEND_URL
                download_url = f"{BACKEND_URL}/api/v1/projects/{project_id}/download/{excel_file}"
                st.markdown(
                    f"[📥 点击下载 Excel 文件]({download_url})"
                )

            # ── 刷新页面以更新侧边栏状态 ────────────
            time.sleep(2)
            st.rerun()

        except Exception as exc:
            status_placeholder.error("❌ 一键生成失败")
            show_error("一键生成", exc)


def render_batch_section() -> None:
    """渲染批量生成区域。"""
    st.markdown("---")
    st.subheader("📦 批量生成")

    try:
        projects = list_projects()
    except Exception:
        projects = []

    ready = [p for p in projects if p.get("status") in ("parsed", "features_extracted")]
    if len(ready) < 2:
        st.caption("需至少 2 个已上传文档的项目才能批量生成")
        return

    options = {p["id"]: f"{p['name']} ({p.get('status','')})" for p in ready}
    selected = st.multiselect("选择要批量处理的项目", options.keys(), format_func=lambda x: options[x])

    if selected and st.button(f"📦 批量生成（{len(selected)} 个项目）", type="primary"):
        with st.spinner(f"正在并行处理 {len(selected)} 个项目..."):
            try:
                result = batch_generate(list(selected))
                data = result.get("data", {})
                st.success(f"✅ {data.get('success', 0)} 成功 / {data.get('failed', 0)} 失败")
                for r in data.get("results", []):
                    if r.get("ok"):
                        st.success(f"✅ P{r['project_id']} {r.get('name','')}: {r.get('doc_type','自动识别')} F={r['counts'].get('features',0)} TP={r['counts'].get('testpoints',0)} TC={r['counts'].get('testcases',0)}")
                    else:
                        st.warning(f"⚠️ P{r['project_id']}: {r.get('error','')}")
            except Exception as exc:
                st.error(f"批量生成失败: {exc}")


# ══════════════════════════════════════════════════════════
# 页面渲染
# ══════════════════════════════════════════════════════════

st.title("📄 项目与文档管理")

# ── 显示当前选中项目 ──────────────────────────────
current_id = st.session_state.get("project_id")
current_name = st.session_state.get("project_name", "")
if current_id:
    st.success(f"📌 当前项目: **{current_name}** (ID: {current_id})")

# ── 渲染各部分 ────────────────────────────────────
render_project_list()
render_upload_section()
render_one_click_section()
render_batch_section()

from frontend.utils.localize import inject_localize
inject_localize()
