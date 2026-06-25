"""
UX 工具 — 用户友好的错误提示
=============================
统一错误消息格式，避免向用户暴露技术细节。
"""

import streamlit as st


def show_success_then_rerun(msg: str, delay: float = 1.5) -> None:
    """显示成功消息并延迟 rerun（让用户看到提示）。

    Args:
        msg: 成功消息
        delay: 延迟秒数
    """
    import streamlit as st
    import time
    st.success(msg)
    time.sleep(delay)
    st.rerun()


def show_error(context: str, exc: Exception | None = None) -> None:
    """显示用户友好的错误消息。

    Args:
        context: 操作场景描述（如"功能点提取"、"文档上传"）
        exc: 原始异常（仅用于日志，不会显示给用户）
    """
    messages = {
        "功能点提取": "功能点提取失败，请确认文档内容清晰且网络正常",
        "测试点生成": "测试点生成失败，请确认已提取功能点且网络正常",
        "测试用例生成": "测试用例生成失败，请确认已生成测试点且网络正常",
        "文档上传": "文档上传失败，请检查文件格式（支持 TXT/DOCX/PDF/MD）",
        "Excel导出": "导出失败，请确认已生成测试用例",
        "一键生成": "一键生成失败，请确认文档已上传且网络正常",
        "项目创建": "项目创建失败，请稍后重试",
        "项目删除": "项目删除失败，请稍后重试",
        "加载数据": "加载数据失败，请检查后端服务是否正常运行",
        "添加": "添加失败，请检查输入内容",
        "更新": "更新失败，请稍后重试",
        "删除": "删除失败，请稍后重试",
    }

    friendly = messages.get(context, f"{context}失败，请稍后重试")
    st.error(f"❌ {friendly}")


def show_warning(context: str) -> None:
    """显示警告消息。

    Args:
        context: 场景描述
    """
    st.warning(f"⚠️ {context}")
