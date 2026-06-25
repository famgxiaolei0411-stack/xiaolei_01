"""
共享侧边栏组件 — 在每个页面显示当前项目状态
==============================================
"""

import streamlit as st
from frontend.utils.session import SessionKeys
from frontend.utils.constants import BACKEND_URL


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
            project_status = project.get("status", project_status)
            st.session_state[SessionKeys.PROJECT_STATUS] = project_status
        except Exception as exc:
            status_sync_error = str(exc)

    with st.sidebar:
        st.markdown("## 🧪 AI Test Copilot")

        try:
            from frontend.utils.api_client import health_check
            health = health_check()
            ai = health.get("ai", {})
            st.success("后端已连接")
            st.caption(f"后端: {BACKEND_URL}")
            if ai.get("configured"):
                st.caption(f"AI: {ai.get('provider', '-')}/{ai.get('model', '-')}")
            else:
                st.warning("AI Key 未配置，生成能力不可用")
                st.caption("请复制 .env.example 为 .env，并填写 API Key")
        except Exception:
            st.error("后端未连接")
            st.caption("请先运行 start.bat，或手动启动 FastAPI 后端")

        if status_sync_error:
            st.caption(f"项目状态同步失败，显示本地缓存: {status_sync_error}")

        st.markdown("---")

        if project_id:
            st.success(f"📌 **{project_name}**")

            steps = [
                ("parsed", "📄 文档已上传"),
                ("features_extracted", "🔍 功能点已提取"),
                ("testpoints_generated", "📋 测试点已生成"),
                ("testcases_generated", "📝 用例已生成"),
                ("exported", "📥 已导出"),
            ]
            current_idx = -1
            for i, (key, _label) in enumerate(steps):
                if project_status == key:
                    current_idx = i

            for i, (_key, label) in enumerate(steps):
                if i <= current_idx:
                    st.markdown(f"✅ {label}")
                elif i == current_idx + 1:
                    st.markdown(f"➡️ **{label}** ← 当前步骤")
                else:
                    st.markdown(f"⏳ {label}")

            st.markdown("---")
            st.caption("💡 切换左侧页面不会丢失数据，所有结果已保存到数据库。")
        else:
            st.warning("⚠️ 未选择项目")
            st.caption("请先在「📄 上传文档」页面创建或选择项目")

        st.markdown("---")
