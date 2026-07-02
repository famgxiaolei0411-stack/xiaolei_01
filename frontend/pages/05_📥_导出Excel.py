"""
导出 Excel 页面 — 导出与下载
===============================
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))


import streamlit as st
import pandas as pd

from frontend.utils.api_client import (
    export_excel,
    get_document,
    list_features,
    list_testpoints,
    list_testcases,
    get_testcase_review,
    get_download_url,
)
from frontend.utils.constants import APP_TITLE, BACKEND_URL
from frontend.utils.session import init_session
from frontend.components.sidebar import render_sidebar
from frontend.components.platform_widgets import (
    format_file_size,
    render_api_contract_metrics,
    render_quality_score_card,
    render_table_filters,
)
from frontend.utils.ux import show_error

st.set_page_config(
    page_title=f"导出 Excel - {APP_TITLE}",
    page_icon="📥",
    layout="wide",
)

init_session()
render_sidebar()

st.title("📥 导出 Excel")

# ── 检查项目 ──────────────────────────────────────
project_id = st.session_state.get("project_id")
if not project_id:
    st.warning("⚠️ 请先在「上传文档」页面选择或创建项目")
    st.stop()


# ══════════════════════════════════════════════════════════
# 数据概览
# ══════════════════════════════════════════════════════════

def render_overview() -> None:
    """渲染数据概览。"""
    st.subheader("📊 数据概览")

    try:
        f_result = list_features(project_id)
        tp_result = list_testpoints(project_id)
        tc_result = list_testcases(project_id)

        features = f_result.get("data", {}).get("features", [])
        testpoints = tp_result.get("data", {}).get("testpoints", [])
        testcases = tc_result.get("data", {}).get("testcases", [])
    except Exception as exc:
        show_error("加载数据", exc)
        features, testpoints, testcases = [], [], []

    col1, col2, col3 = st.columns(3)
    col1.metric("功能点", len(features))
    col2.metric("测试点", len(testpoints))
    col3.metric("测试用例", len(testcases))

    try:
        review_result = get_testcase_review(project_id)
        review = review_result.get("data", {}) or {}
        metrics = review.get("metrics", {}) or {}
        render_quality_score_card(review)
        render_api_contract_metrics(metrics)
    except Exception as exc:
        st.caption("暂无可用质量评审，仍可查看数据并尝试导出。")
        with st.expander("查看质量评审加载细节"):
            st.code(str(exc))

    # ── 预览测试用例 ──────────────────────────────
    if testcases:
        st.markdown("---")
        st.subheader("📋 测试用例预览")

        preview_data = []
        for tc in testcases[:20]:  # 仅显示前 20 条
            steps = tc.get("steps", [])
            if isinstance(steps, list):
                steps_text = "\n".join(f"{i+1}. {s}" for i, s in enumerate(steps))
            else:
                steps_text = str(steps)

            preview_data.append({
                "编号": tc.get("case_id", ""),
                "标题": tc.get("title", ""),
                "优先级": tc.get("priority", ""),
                "类型": tc.get("case_type", ""),
                "步骤": steps_text[:100] + ("..." if len(steps_text) > 100 else ""),
            })

        df = pd.DataFrame(preview_data)
        filtered_df = render_table_filters(
            df,
            key_prefix="export_preview",
            search_columns=["编号", "标题", "步骤"],
            filter_columns=["优先级", "类型"],
        )
        st.dataframe(filtered_df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════
# 导出操作
# ══════════════════════════════════════════════════════════

def render_export_section() -> None:
    """渲染导出操作区域。"""
    st.markdown("---")
    st.subheader("📥 导出 Excel")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("""
        ### 导出内容

        生成的 Excel 文件包含以下工作表：

        | 工作表 | 内容 |
        |--------|------|
        | **功能点清单** | 模块、名称、描述、优先级、前置条件、业务规则 |
        | **测试点清单** | 关联功能点、测试类型、描述、预期结果、测试数据、优先级 |
        | **测试用例清单** | 需求文档导出功能用例列；接口文档导出接口用例列 |

        ### 样式特性

        - ✅ 标题行冻结（滚动时保持可见）
        - ✅ 自动筛选（可按优先级、类型筛选）
        - ✅ 优先级颜色标记（P0 红、P1 黄、P2 绿、P3 浅绿）
        - ✅ 自适应行高（多行文本完整显示）
        - ✅ 自动列宽
        """)

    with col2:
        st.markdown("### 🚀 导出操作")

        fmt = st.selectbox("导出格式", ["excel", "json", "md"],
                          format_func=lambda x: {"excel": "📊 Excel (.xlsx)", "json": "📋 JSON (.json)", "md": "📝 Markdown (.md)"}[x])
        fmt_label = {"excel": "Excel", "json": "JSON", "md": "Markdown"}[fmt]
        detected_mode = "functional"
        try:
            doc_result = get_document(project_id)
            detected_mode = doc_result.get("data", {}).get("testcase_mode", "functional")
        except Exception:
            pass

        mode_options = {
            "auto": "自动识别",
            "api": "接口测试模板",
            "functional": "功能测试模板",
        }
        testcase_mode = "auto"
        if fmt == "excel":
            testcase_mode = st.radio(
                "测试用例表头",
                options=list(mode_options.keys()),
                format_func=lambda key: mode_options[key],
                index=0,
                horizontal=False,
                help="如果自动识别不准，可以手动指定导出的测试用例模板。",
            )
            if testcase_mode == "auto":
                st.caption(
                    f"当前自动识别结果：{'接口测试模板' if detected_mode == 'api' else '功能测试模板'}"
                )

        try:
            tc_result = list_testcases(project_id)
            testcases = tc_result.get("data", {}).get("testcases", [])
        except Exception:
            testcases = []

        review = {}
        try:
            review = get_testcase_review(project_id).get("data", {}) or {}
        except Exception:
            pass

        if not testcases:
            st.warning("当前项目暂无测试用例，建议先生成测试用例后再导出。")
        elif review and not review.get("pass", True):
            st.warning("质量评审未通过，建议先修正高风险问题后再导出。")
        api_contract = (
            (review.get("metrics", {}) or {})
            .get("skill_reviews", {})
            .get("api_contract")
        )
        if api_contract and float(api_contract.get("contract_complete_ratio", 1) or 0) < 1:
            st.warning("接口契约检查未完全通过，建议补充 method、url 或响应断言。")

        if st.button(f"📥 导出 {fmt_label}", type="primary", use_container_width=True):
            with st.spinner(f"正在生成 {fmt_label} 文件..."):
                try:
                    result = export_excel(project_id, fmt, testcase_mode)
                    download_url = get_download_url(result.get("download_url", ""))

                    st.success(f"✅ {fmt_label} 文件生成成功！")
                    st.info(
                        f"📄 文件名: {result.get('filename')}\n\n"
                        f"📏 文件大小: {result.get('file_size', 0):,} 字节"
                    )

                    st.markdown(
                        f"[📥 点击下载 {fmt_label} 文件]({download_url})"
                    )

                    st.session_state["project_status"] = "exported"

                except Exception as exc:
                    show_error("Excel导出", exc)

    # ── 手动下载（如果之前已导出）─────────────────
    st.markdown("---")
    st.subheader("📂 历史导出文件")

    import os
    from config import OUTPUT_DIR

    project_name = st.session_state.get("project_name", "")
    safe_prefix = f"{project_name}_" if project_name else ""
    export_files = [
        path for path in list(OUTPUT_DIR.glob("*.xlsx")) + list(OUTPUT_DIR.glob("*.json")) + list(OUTPUT_DIR.glob("*.md"))
        if not safe_prefix or path.name.startswith(safe_prefix)
    ]
    if export_files:
        export_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

        for f_path in export_files[:10]:
            f_name = f_path.name
            f_size = f_path.stat().st_size
            f_time = f_path.stat().st_mtime
            f_type = f_path.suffix.lstrip(".").upper() or "FILE"

            from datetime import datetime
            time_str = datetime.fromtimestamp(f_time).strftime("%Y-%m-%d %H:%M:%S")

            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            with col1:
                st.markdown(f"📄 **{f_name}** — {time_str}")
            with col2:
                st.caption(f_type)
            with col3:
                st.caption(format_file_size(f_size))
            with col4:
                download_link = f"{BACKEND_URL}/api/v1/projects/{project_id}/download/{f_name}"
                st.markdown(f"[📥 下载]({download_link})")
    else:
                st.info("📭 暂无导出文件 — 请先完成测试用例生成，然后点击「导出 Excel」")


def render_quality_review() -> None:
    """渲染质量评审摘要。"""
    st.markdown("---")
    st.subheader("🧪 质量评审")
    try:
        result = get_testcase_review(project_id)
        review = result.get("data", {}) or {}
    except Exception as exc:
        show_error("加载数据", exc)
        return

    metrics = review.get("metrics", {}) or {}
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("评分", review.get("score", 0))
    col2.metric("P0 占比", f"{metrics.get('p0_ratio', 0):.0%}")
    col3.metric("重复编号", metrics.get("duplicate_case_ids", 0))
    col4.metric("用例总数", metrics.get("total", 0))

    if review.get("pass"):
        st.success(review.get("summary", "质量评审通过"))
    else:
        st.warning(review.get("summary", "质量评审未通过"))

    render_api_contract_metrics(metrics)

    issues = review.get("issues", []) or []
    if issues:
        st.markdown("**问题清单**")
        for issue in issues[:8]:
            st.write(f"- {issue.get('level', 'info')}: {issue.get('msg', '')}")


# ── 渲染 ──────────────────────────────────────────
render_overview()
render_export_section()
render_quality_review()

from frontend.utils.localize import inject_localize
inject_localize()
