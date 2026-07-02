"""
共享侧边栏组件 — 在每个页面显示当前项目状态
==============================================
"""

import streamlit as st
from frontend.utils.session import SessionKeys
from frontend.utils.constants import BACKEND_URL
from frontend.components.platform_widgets import (
    render_next_action_hint,
    render_process_stepper,
    render_project_status_card,
)


STATUS_RANK = {
    "": -1,
    "parsed": 0,
    "extracting": 1,
    "features_extracted": 2,
    "generating_testpoints": 3,
    "testpoints_generated": 4,
    "generating_testcases": 5,
    "testcases_generated": 6,
    "exporting": 7,
    "exported": 8,
}
PROCESSING_STATUSES = {"extracting", "generating_testpoints", "generating_testcases", "exporting"}
MILESTONE_STEPS = [
    ("parsed", "📄 文档已上传"),
    ("features_extracted", "🔍 功能点已提取"),
    ("testpoints_generated", "📋 测试点已生成"),
    ("testcases_generated", "📝 用例已生成"),
    ("exported", "📥 已导出"),
]
PROCESSING_LABELS = {
    "extracting": "🔍 正在提取功能点",
    "generating_testpoints": "📋 正在生成测试点",
    "generating_testcases": "📝 正在生成用例",
    "exporting": "📥 正在导出",
}


def _inject_sidebar_style() -> None:
    """优化 Streamlit 默认侧边栏导航样式。"""
    st.markdown(
        """
<style>
[data-testid="stSidebarNav"] li:has(a[href$="/app"]) {
    display: none;
}
[data-testid="stSidebarNav"] ul {
    padding-top: 0.75rem;
}
[data-testid="stSidebarNav"] a {
    border-radius: 8px;
    margin: 2px 10px;
    padding: 9px 12px;
    color: #374151;
    font-weight: 600;
}
[data-testid="stSidebarNav"] a:hover {
    background: #eef3ff;
    color: #1f3a8a;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: #e7eefc;
    color: #1e2f5c;
}
</style>
""",
        unsafe_allow_html=True,
    )


def _merge_project_status(local_status: str, remote_status: str | None) -> str:
    """合并本地和后端状态，避免处理中的本地进度被旧后端状态覆盖。"""
    if not remote_status:
        return local_status
    if local_status in PROCESSING_STATUSES:
        local_rank = STATUS_RANK.get(local_status, -1)
        remote_rank = STATUS_RANK.get(remote_status, -1)
        if remote_rank < local_rank:
            return local_status
    if STATUS_RANK.get(remote_status, -1) >= STATUS_RANK.get(local_status, -1):
        return remote_status
    return local_status


def _render_ai_status(health: dict) -> None:
    """显示 AI 配置状态，兼容旧后端未返回 ai 字段的情况。"""
    ai = health.get("ai")
    st.success("后端已连接")
    st.caption(f"后端: {BACKEND_URL}")

    if isinstance(ai, dict):
        if ai.get("configured"):
            st.caption(f"AI: {ai.get('provider', '-')}/{ai.get('model', '-')}")
        else:
            st.warning("AI Key 未配置，生成能力不可用")
            st.caption("请复制 .env.example 为 .env，并填写 API Key")
    else:
        st.info("当前后端未返回 AI 配置状态")
        st.caption("如已配置 Key，请确认前端连接的是最新启动的后端")


def render_sidebar() -> None:
    """在所有页面侧边栏显示项目状态和工作流进度。"""
    _inject_sidebar_style()

    project_id = st.session_state.get(SessionKeys.PROJECT_ID)
    project_name = st.session_state.get(SessionKeys.PROJECT_NAME, "")
    project_status = st.session_state.get(SessionKeys.PROJECT_STATUS, "")
    status_sync_error = ""

    if project_id:
        try:
            from frontend.utils.api_client import get_project
            project = get_project(project_id)
            project_status = _merge_project_status(project_status, project.get("status"))
            st.session_state[SessionKeys.PROJECT_STATUS] = project_status
        except Exception as exc:
            status_sync_error = str(exc)

    with st.sidebar:
        st.markdown("## 🧪 AI Test Copilot")

        try:
            from frontend.utils.api_client import health_check
            _render_ai_status(health_check())
        except Exception:
            st.error("后端未连接")
            st.caption("请先运行 start.bat，或手动启动 FastAPI 后端")

        if status_sync_error:
            st.caption(f"项目状态同步失败，显示本地缓存: {status_sync_error}")

        st.markdown("---")

        render_project_status_card(
            project_id=project_id,
            project_name=project_name,
            status=project_status,
            doc_type=st.session_state.get(SessionKeys.DOC_TYPE, ""),
            testcase_mode=st.session_state.get(SessionKeys.TESTCASE_MODE, ""),
        )

        st.markdown("#### 流程进度")
        render_process_stepper(project_status)
        render_next_action_hint(project_status)

        st.markdown("---")
