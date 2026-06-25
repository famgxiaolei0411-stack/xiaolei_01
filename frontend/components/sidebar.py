"""
共享侧边栏组件 — 在每个页面显示当前项目状态
==============================================
"""

import streamlit as st
from frontend.utils.session import SessionKeys, init_session


def render_sidebar() -> None:
    """在所有页面侧边栏显示项目状态和工作流进度。

    调用方式：在每个页面的 st.set_page_config() 之后调用。
    """
    project_id = st.session_state.get(SessionKeys.PROJECT_ID)
    project_name = st.session_state.get(SessionKeys.PROJECT_NAME, "")
    project_status = st.session_state.get(SessionKeys.PROJECT_STATUS, "")

    # 从后端实时拉取最新状态，确保侧边栏同步
    if project_id:
        try:
            from frontend.utils.api_client import get_project
            proj = get_project(project_id)
            project_status = proj.get("status", project_status)
            st.session_state[SessionKeys.PROJECT_STATUS] = project_status
        except Exception:
            pass  # 后端不可用时使用 session 缓存

    with st.sidebar:
        st.markdown("## 🧪 AI Test Copilot")

        if project_id:
            st.success(f"📌 **{project_name}**")

            # ── 工作流进度指示 ────────────────────
            steps = [
                ("parsed", "📄 文档已上传"),
                ("features_extracted", "🔍 功能点已提取"),
                ("testpoints_generated", "📋 测试点已生成"),
                ("testcases_generated", "📝 用例已生成"),
                ("exported", "📥 已导出"),
            ]
            current_idx = -1
            for i, (key, label) in enumerate(steps):
                if project_status == key:
                    current_idx = i

            for i, (key, label) in enumerate(steps):
                if i <= current_idx:
                    st.markdown(f"✅ {label}")
                elif i == current_idx + 1:
                    st.markdown(f"➡️ **{label}** ← 当前步骤")
                else:
                    st.markdown(f"⏳ {label}")

            st.markdown("---")
            st.caption(
                "💡 切换左侧页面不会丢失数据，"
                "所有结果已保存到数据库。"
            )
        else:
            st.warning("⚠️ 未选择项目")
            st.caption("请先在「📄 上传文档」页面创建或选择项目")

        st.markdown("---")
