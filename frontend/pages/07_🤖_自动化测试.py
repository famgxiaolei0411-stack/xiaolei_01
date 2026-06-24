"""
自动化测试页面 — 生成 Pytest 脚本、执行测试、查看 Allure 报告
=============================================================
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from frontend.utils.api_client import (
    generate_test_script,
    run_test,
    run_auto_pipeline,
    list_test_scripts,
    get_allure_report_url,
)
from frontend.utils.session import init_session
from frontend.components.sidebar import render_sidebar
from frontend.utils.constants import APP_TITLE

st.set_page_config(
    page_title=f"自动化测试 - {APP_TITLE}",
    page_icon="🤖",
    layout="wide",
)

init_session()
render_sidebar()


def _friendly_error(exc: Exception) -> str:
    """提取 HTTP 响应中的友好错误消息。"""
    try:
        # httpx.HTTPStatusError 包含服务端返回的 detail
        if hasattr(exc, "response"):
            body = exc.response.json()
            return body.get("detail", body.get("message", str(exc)))
    except Exception:
        pass
    # 简洁的通用消息
    msg = str(exc)
    if "400" in msg:
        return "请先生成测试用例"
    if "404" in msg:
        return "资源不存在"
    if "500" in msg:
        return "服务器内部错误，请稍后重试"
    return msg[:100]


# ══════════════════════════════════════════════════════════
# 页面渲染
# ══════════════════════════════════════════════════════════

st.title("🤖 自动化测试")

project_id = st.session_state.get("project_id")
project_name = st.session_state.get("project_name", "")
if not project_id:
    st.warning("👈 请先在「上传文档」页面创建或选择项目")
    st.stop()

st.success(f"📌 当前项目: **{project_name}** (ID: {project_id})")

# ── 三个操作区 ────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["⚡ 一键执行", "📝 生成脚本", "▶️ 执行测试"])

# ══════════════════════════════════════════════════════════
# Tab 1: 一键执行（推荐）
# ══════════════════════════════════════════════════════════

with tab1:
    st.subheader("⚡ 一键自动化测试管线")

    st.markdown("""
    一键完成全部自动化测试流程：

    **测试用例 → 生成 Pytest 脚本 → pytest 执行 → Allure 报告**
    """)

    col1, col2 = st.columns(2)
    with col1:
        module_name = st.text_input(
            "模块名称",
            value=project_name or "通用模块",
            help="用于生成的测试类名和文件名",
            key="pipe_module",
        )
    with col2:
        base_url = st.text_input(
            "被测系统 URL",
            value="http://localhost:8000",
            help="测试脚本中的 BASE_URL",
            key="pipe_url",
        )

    if st.button("⚡ 启动自动化管线", type="primary", use_container_width=True):
        with st.spinner("管线执行中，请耐心等待..."):
            try:
                result = run_auto_pipeline(project_id, module_name, base_url)
                data = result.get("data", {})

                st.success(f"✅ {result.get('message', '管线完成')}")
                st.balloons()

                # ── 统计卡片 ────────────────────────
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("总用例数", data.get("total", 0))
                col2.metric("✅ 通过", data.get("passed", 0))
                col3.metric("❌ 失败", data.get("failed", 0))
                col4.metric("📈 通过率", f"{data.get('pass_rate', 0):.1%}")

                # ── 摘要 ────────────────────────────
                st.info(f"**执行摘要**: {data.get('summary', '')}")
                st.caption(
                    f"耗时: {data.get('duration', 0):.1f}s | "
                    f"脚本: {data.get('script_file', '')}"
                )

                # ── Allure 报告链接 ──────────────────
                allure_url = get_allure_report_url(project_id)
                st.markdown(
                    f"[📊 查看 Allure 详细报告]({allure_url})"
                )

            except Exception as exc:
                msg = _friendly_error(exc)
                st.error(f"❌ {msg}")
                if "测试用例" in msg:
                    st.info("💡 请先完成「功能点提取 → 测试点生成 → 测试用例生成」")
                else:
                    st.info("💡 请确认 pytest + allure-pytest 已安装")


# ══════════════════════════════════════════════════════════
# Tab 2: 生成脚本
# ══════════════════════════════════════════════════════════

with tab2:
    st.subheader("📝 生成测试框架")

    st.markdown("""
    生成完整的**分层 Pytest + Allure 自动化测试框架**：

    ```
    config/ → api/base_api.py → utils/ → data/{module}.json → case/test_*.py → run.py
    ```

    特性：BaseApi 请求封装、Allure 自动附件、JSON 数据驱动、分层断言
    """)

    col1, col2 = st.columns(2)
    with col1:
        gen_module = st.text_input(
            "模块名称",
            value=project_name or "通用模块",
            key="gen_module",
        )
    with col2:
        gen_url = st.text_input(
            "被测系统 URL",
            value="http://localhost:8000",
            key="gen_url",
        )

    if st.button("📝 生成测试脚本", type="primary", use_container_width=True):
        with st.spinner("正在生成测试脚本..."):
            try:
                result = generate_test_script(project_id, gen_module, gen_url)
                data = result.get("data", {})
                st.success(f"✅ {result.get('message', '生成成功')}")
                st.metric("用例数", data.get("testcase_count", 0))
                st.code(data.get("filename", ""), language="text")
                st.caption(f"文件路径: {data.get('filepath', '')}")
            except Exception as exc:
                st.error(f"❌ {_friendly_error(exc)}")

    # ── 已有脚本列表 ────────────────────────────────
    st.markdown("---")
    st.markdown("**📂 已生成的测试脚本**")

    if st.button("🔄 刷新脚本列表"):
        st.rerun()

    try:
        scripts_result = list_test_scripts(project_id)
        scripts_data = scripts_result.get("data", {})
        scripts = scripts_data.get("scripts", [])

        if not scripts:
            st.info("📭 暂无测试框架 — 请先生成测试用例，然后点击「生成测试框架」")
        else:
            for s in scripts:
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                with col1:
                    st.code(s["project_name"], language="text")
                with col2:
                    st.caption(f"{s.get('case_files', 0)} 个文件")
                with col3:
                    if st.button("📂 查看", key=f"view_{s['project_name']}"):
                        st.session_state["view_framework"] = s["project_name"]
                        st.rerun()
                with col4:
                    if st.button("🗑️ 删除", key=f"del_{s['project_name']}"):
                        try:
                            from frontend.utils.api_client import delete_framework
                            delete_framework(project_id, s["project_name"])
                            st.success(f"已删除 {s['project_name']}")
                            import time; time.sleep(1); st.rerun()
                        except Exception as exc:
                            st.error(f"删除失败: {exc}")

    except Exception as exc:
        st.warning(f"⚠️ 获取框架列表失败: {exc}")

    # ── 文件浏览器 ────────────────────────────────
    if st.session_state.get("view_framework"):
        fw_name = st.session_state["view_framework"]
        st.markdown("---")
        st.subheader(f"📂 {fw_name}")

        try:
            from frontend.utils.api_client import list_framework_files, view_framework_file

            files_result = list_framework_files(project_id, fw_name)
            all_files = files_result.get("data", {}).get("files", [])

            # 按目录分组
            dirs: dict[str, list] = {}
            for f in all_files:
                d = f.get("dir", "") or "(根目录)"
                dirs.setdefault(d, []).append(f)

            # 选择要查看的文件
            file_options = [(f["path"], f"{f['dir']}/{f['name']}" if f['dir'] else f['name'])
                          for f in all_files]
            if file_options:
                selected = st.selectbox(
                    "选择文件查看",
                    options=[p for p, _ in file_options],
                    format_func=lambda p: next((n for fp, n in file_options if fp == p), p),
                    key="file_selector",
                )

                if selected:
                    content_result = view_framework_file(project_id, fw_name, selected)
                    file_data = content_result.get("data", {})
                    lang = file_data.get("language", "python")
                    st.code(file_data.get("content", ""), language=lang)
                    st.caption(f"{selected} ({file_data.get('size', 0):,} 字节)")

            if st.button("❌ 关闭", key="close_viewer"):
                st.session_state.pop("view_framework", None)
                st.rerun()

        except Exception as exc:
            st.warning(f"⚠️ 加载文件失败: {exc}")


# ══════════════════════════════════════════════════════════
# Tab 3: 执行测试
# ══════════════════════════════════════════════════════════

with tab3:
    st.subheader("▶️ 执行 Pytest 测试")

    st.markdown("""
    选择已生成的测试框架项目并执行，自动产出 **Allure HTML 报告**。
    """)

    # ── 获取框架列表用于选择 ────────────────────────
    try:
        scripts_result = list_test_scripts(project_id)
        scripts_data = scripts_result.get("data", {})
        scripts = scripts_data.get("scripts", [])
        project_dirs = [(s["project_dir"], s["project_name"]) for s in scripts]
    except Exception as exc:
        st.warning(f"⚠️ 获取框架列表失败: {exc}")
        project_dirs = []

    if not project_dirs:
        st.warning("⚠️ 没有可执行的测试框架，请先在「生成测试框架」标签页生成")
    else:
        selected_dir, selected_name = st.selectbox(
            "选择测试框架项目",
            options=project_dirs,
            format_func=lambda x: x[1],
            help="选择要执行的测试框架项目",
        )

        if st.button("▶️ 执行测试", type="primary", use_container_width=True):
            with st.spinner(f"正在执行 {selected_name}..."):
                try:
                    result = run_test(project_id, selected_dir)
                    data = result.get("data", {})

                    st.success(f"✅ {result.get('message', '执行完成')}")

                    # ── 统计 ────────────────────────
                    col1, col2, col3, col4, col5 = st.columns(5)
                    col1.metric("总计", data.get("total", 0))
                    col2.metric("✅ 通过", data.get("passed", 0))
                    col3.metric("❌ 失败", data.get("failed", 0))
                    col4.metric("⏭️ 跳过", data.get("skipped", 0))
                    col5.metric("📈 通过率", f"{data.get('pass_rate', 0):.1%}")

                    st.info(data.get("summary", ""))

                    # ── Allure 报告链接 ──────────────
                    allure_url = get_allure_report_url(project_id)
                    st.markdown(
                        f"[📊 查看 Allure 详细报告]({allure_url})"
                    )

                except Exception as exc:
                    st.error(f"❌ {_friendly_error(exc)}")
                    st.info(
                        "💡 请确认：1) pytest + allure-pytest 已安装 "
                        "2) allure 命令行工具已安装 "
                        "3) 测试脚本没有语法错误"
                    )


st.markdown("---")
st.caption("自动化测试 | Powered by Pytest + Allure")

from frontend.utils.localize import inject_localize
inject_localize()
