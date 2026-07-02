"""Shared Streamlit widgets for the platform-style frontend."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


STATUS_LABELS = {
    "": "未开始",
    "created": "已创建",
    "parsed": "文档已上传",
    "extracting": "正在提取功能点",
    "features_extracted": "功能点已提取",
    "generating_testpoints": "正在生成测试点",
    "testpoints_generated": "测试点已生成",
    "generating_testcases": "正在生成测试用例",
    "testcases_generated": "测试用例已生成",
    "exporting": "正在导出",
    "exported": "已导出",
}

STEP_RANK = {
    "": -1,
    "created": -1,
    "parsed": 0,
    "extracting": 1,
    "features_extracted": 1,
    "generating_testpoints": 2,
    "testpoints_generated": 2,
    "generating_testcases": 3,
    "testcases_generated": 4,
    "exporting": 5,
    "exported": 5,
}

PROCESS_STEPS = [
    ("文档", 0),
    ("功能点", 1),
    ("测试点", 2),
    ("测试用例", 3),
    ("质量评审", 4),
    ("导出", 5),
]


def render_project_status_card(
    *,
    project_id: int | None,
    project_name: str = "",
    status: str = "",
    doc_type: str = "",
    testcase_mode: str = "",
) -> None:
    """Render a compact project status card with graceful empty state."""

    with st.container(border=True):
        if not project_id:
            st.warning("未选择项目")
            st.caption("请先在「上传文档」页面创建或选择项目。")
            return

        st.markdown(f"**{project_name or '未命名项目'}**")
        st.caption(f"项目 ID: {project_id}")
        st.metric("当前状态", STATUS_LABELS.get(status, status or "待同步"))

        detail_parts = []
        if doc_type:
            detail_parts.append(f"文档类型: {doc_type}")
        if testcase_mode:
            mode_label = "接口测试" if testcase_mode == "api" else "功能测试"
            detail_parts.append(f"用例模式: {mode_label}")
        if detail_parts:
            st.caption(" | ".join(detail_parts))


def render_process_stepper(status: str) -> None:
    """Render a simple process stepper based on current project status."""

    current = STEP_RANK.get(status, -1)
    cols = st.columns(len(PROCESS_STEPS))
    for col, (label, rank) in zip(cols, PROCESS_STEPS):
        if current > rank:
            col.success(f"完成\n{label}")
        elif current == rank:
            col.info(f"当前\n{label}")
        else:
            col.caption(f"待办\n{label}")


def render_next_action_hint(status: str) -> None:
    """Render the most likely next action for the current status."""

    hints = {
        "": "请先创建或选择项目。",
        "created": "请上传需求文档或接口文档。",
        "parsed": "下一步：提取功能点，或使用一键生成。",
        "features_extracted": "下一步：生成测试点。",
        "testpoints_generated": "下一步：生成测试用例。",
        "testcases_generated": "下一步：查看质量评审并导出。",
        "exported": "当前项目已完成导出，可继续下载或维护用例。",
    }
    st.caption(hints.get(status, STATUS_LABELS.get(status, "请等待当前任务完成。")))


def render_skill_badges(skills: list[str], title: str = "已启用 Skill") -> None:
    """Render enabled skill labels without requiring backend configuration."""

    if not skills:
        return
    with st.container(border=True):
        st.caption(title)
        st.write(" · ".join(f"`{skill}`" for skill in skills))


def render_quality_score_card(review: dict[str, Any] | None) -> None:
    """Render quality score summary, tolerating missing review data."""

    if not review:
        st.info("暂无质量评审数据")
        return

    score = int(review.get("score", 0) or 0)
    passed = bool(review.get("pass", False))
    summary = review.get("summary", "") or "暂无评审摘要"
    issues = review.get("issues", []) or []

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        col1.metric("质量评分", score)
        col2.metric("评审状态", "通过" if passed else "需改进")
        col3.metric("问题数", len(issues))
        if passed:
            st.success(summary)
        else:
            st.warning(summary)


def render_api_contract_metrics(metrics: dict[str, Any] | None) -> None:
    """Render ApiContractSkill metrics if present."""

    api_contract = (
        (metrics or {})
        .get("skill_reviews", {})
        .get("api_contract")
    )
    if not api_contract:
        st.caption("暂无接口契约检查指标")
        return

    with st.container(border=True):
        st.caption("接口契约检查")
        col1, col2, col3 = st.columns(3)
        col1.metric("检查用例", api_contract.get("checked", 0))
        col2.metric("契约完整", api_contract.get("contract_complete", 0))
        ratio = float(api_contract.get("contract_complete_ratio", 0) or 0)
        col3.metric("完整率", f"{ratio:.0%}")

        col4, col5, col6 = st.columns(3)
        col4.metric("缺 method", api_contract.get("missing_method", 0))
        col5.metric("缺 url", api_contract.get("missing_url", 0))
        col6.metric("弱断言", api_contract.get("weak_expected", 0))


def filter_dataframe(
    df: pd.DataFrame,
    *,
    search: str = "",
    search_columns: list[str] | None = None,
    filters: dict[str, list[Any]] | None = None,
) -> pd.DataFrame:
    """Filter a DataFrame while tolerating missing columns."""

    if df is None or df.empty:
        return df

    filtered = df.copy()

    if search:
        columns = [col for col in (search_columns or list(filtered.columns)) if col in filtered.columns]
        if columns:
            needle = search.strip().lower()
            mask = pd.Series(False, index=filtered.index)
            for col in columns:
                mask = mask | filtered[col].astype(str).str.lower().str.contains(
                    needle,
                    na=False,
                    regex=False,
                )
            filtered = filtered[mask]

    for col, values in (filters or {}).items():
        if col not in filtered.columns or not values:
            continue
        filtered = filtered[filtered[col].isin(values)]

    return filtered


def render_table_filters(
    df: pd.DataFrame,
    *,
    key_prefix: str,
    search_label: str = "搜索",
    search_columns: list[str] | None = None,
    filter_columns: list[str] | None = None,
) -> pd.DataFrame:
    """Render common search/filter controls and return filtered DataFrame."""

    if df is None or df.empty:
        return df

    search = st.text_input(
        search_label,
        placeholder="输入关键词筛选当前表格",
        key=f"{key_prefix}_search",
    )

    filters: dict[str, list[Any]] = {}
    existing_filter_columns = [
        col for col in (filter_columns or [])
        if col in df.columns
    ]
    if existing_filter_columns:
        cols = st.columns(len(existing_filter_columns))
        for col_widget, column_name in zip(cols, existing_filter_columns):
            options = sorted(
                (
                    value for value in df[column_name].dropna().unique().tolist()
                    if str(value).strip()
                ),
                key=lambda value: str(value),
            )
            filters[column_name] = col_widget.multiselect(
                column_name,
                options,
                key=f"{key_prefix}_{column_name}",
            )

    filtered = filter_dataframe(
        df,
        search=search,
        search_columns=search_columns,
        filters=filters,
    )
    st.caption(f"当前显示 {len(filtered)} / 总计 {len(df)}")
    return filtered


def format_file_size(size: int | float | None) -> str:
    """Format file size for display."""

    value = float(size or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"
