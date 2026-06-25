"""
Streamlit Session 状态管理
============================
管理跨页面的共享状态（当前项目 ID、生成结果等）。
"""

import streamlit as st


class SessionKeys:
    """Session 键名常量。"""
    PROJECT_ID = "project_id"
    PROJECT_NAME = "project_name"
    PROJECT_STATUS = "project_status"
    DOC_FILENAME = "doc_filename"
    DOC_CONTENT = "doc_content"
    DOC_TYPE = "doc_type"
    TESTCASE_MODE = "testcase_mode"
    FEATURES = "features"
    TESTPOINTS = "testpoints"
    TESTCASES = "testcases"
    EXCEL_DOWNLOAD_URL = "excel_download_url"


def init_session() -> None:
    """初始化所有 session 状态变量（如果不存在）。"""
    defaults = {
        SessionKeys.PROJECT_ID: None,
        SessionKeys.PROJECT_NAME: "",
        SessionKeys.PROJECT_STATUS: "",
        SessionKeys.DOC_FILENAME: "",
        SessionKeys.DOC_CONTENT: "",
        SessionKeys.DOC_TYPE: "",
        SessionKeys.TESTCASE_MODE: "",
        SessionKeys.FEATURES: [],
        SessionKeys.TESTPOINTS: [],
        SessionKeys.TESTCASES: [],
        SessionKeys.EXCEL_DOWNLOAD_URL: "",
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def set_project(project_id: int, name: str, status: str = "") -> None:
    """设置当前项目信息，切换项目时自动清除旧缓存。

    Args:
        project_id: 项目 ID
        name: 项目名称
        status: 项目状态
    """
    # 切换到不同项目时清除旧数据缓存
    old_id = st.session_state.get(SessionKeys.PROJECT_ID)
    if old_id and old_id != project_id:
        clear_project()
    st.session_state[SessionKeys.PROJECT_ID] = project_id
    st.session_state[SessionKeys.PROJECT_NAME] = name
    st.session_state[SessionKeys.PROJECT_STATUS] = status


def get_project_id() -> int | None:
    """获取当前项目 ID。"""
    return st.session_state.get(SessionKeys.PROJECT_ID)


def clear_project() -> None:
    """清除当前项目信息及所有关联状态。"""
    # 标准 keys
    for key in (
        SessionKeys.PROJECT_ID,
        SessionKeys.PROJECT_NAME,
        SessionKeys.PROJECT_STATUS,
        SessionKeys.DOC_FILENAME,
        SessionKeys.DOC_CONTENT,
        SessionKeys.DOC_TYPE,
        SessionKeys.TESTCASE_MODE,
        SessionKeys.FEATURES,
        SessionKeys.TESTPOINTS,
        SessionKeys.TESTCASES,
        SessionKeys.EXCEL_DOWNLOAD_URL,
    ):
        st.session_state[key] = None if key == SessionKeys.PROJECT_ID else (
            [] if key in (SessionKeys.FEATURES, SessionKeys.TESTPOINTS, SessionKeys.TESTCASES) else ""
        )
    # 后台生成 & 评审状态（防止跨项目泄漏）
    for trans_key in (
        "generating_testpoints", "tp_gen_result", "tp_gen_error",
        "generating_testcases", "gen_result", "gen_error",
        "case_issues", "review_summary",
    ):
        st.session_state.pop(trans_key, None)
