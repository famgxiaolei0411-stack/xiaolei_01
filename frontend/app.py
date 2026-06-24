"""
AI Test Copilot — Streamlit 主入口
=====================================
多页面应用配置与全局路由。

启动方式:
    streamlit run frontend/app.py
"""

import sys
from pathlib import Path

# 将项目根目录加入 Python 路径（解决 Streamlit 子目录运行时的导入问题）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from frontend.utils.constants import APP_TITLE, APP_SUBTITLE
from frontend.utils.session import init_session

# ── 页面配置 ──────────────────────────────────────
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 初始化 Session ────────────────────────────────
init_session()

# ── 主页面内容 ────────────────────────────────────
st.title(f"🧪 {APP_TITLE}")
st.markdown(f"### {APP_SUBTITLE}")

st.markdown("---")

# ── 快速入门指南 ──────────────────────────────────
st.markdown("""
## 🚀 快速入门

### 操作流程

1. **📄 上传文档** — 上传需求规格说明书（支持 TXT / DOCX / PDF / Markdown）
2. **🔍 功能点提取** — AI 自动从文档中提取功能点
3. **📋 测试点生成** — 基于功能点自动生成测试点
4. **📝 测试用例生成** — 基于测试点生成可执行的测试用例
5. **📥 导出 Excel** — 导出为格式化的 Excel 文件
6. **🧠 RAG 知识库** — 文档向量化 + FAISS 语义检索（V2）
7. **🤖 自动化测试** — 生成 Pytest 脚本 → 执行 → Allure 报告（V2）

### 核心特性

| 特性 | 说明 |
|------|------|
| 🤖 **AI 驱动** | 基于 DeepSeek 大模型，自动分析需求 |
| 📑 **长文档支持** | 自动分块处理，支持 100 页需求文档 |
| ✏️ **人工编辑** | 支持对 AI 生成结果进行增删改 |
| 📊 **专业导出** | 格式化 Excel，含样式、冻结窗格、优先级标记 |
| ⚡ **一键生成** | 从文档到 Excel，全流程自动化 |
| 🧠 **RAG 增强** | FAISS 向量检索 + 上下文增强 Prompt |
| 🤖 **自动执行** | Pytest + Allure 自动执行和报告生成 |

### 当前状态

""")

# ── 显示当前项目状态 ──────────────────────────────
project_id = st.session_state.get("project_id")
project_name = st.session_state.get("project_name", "")

if project_id:
    st.success(f"📌 当前项目: **{project_name}** (ID: {project_id})")
    status = st.session_state.get("project_status", "")
    if status:
        status_map = {
            "created": "🆕 已创建",
            "parsed": "📄 已解析文档",
            "features_extracted": "🔍 已提取功能点",
            "testpoints_generated": "📋 已生成测试点",
            "testcases_generated": "📝 已生成测试用例",
            "exported": "📥 已导出 Excel",
        }
        st.info(f"处理状态: {status_map.get(status, status)}")
else:
    st.warning("👈 请先在**上传文档**页面创建或选择项目")

st.markdown("---")
st.caption("AI Test Copilot v2.0.0 | Powered by DeepSeek + FAISS + Allure")

# ── 侧边栏 ────────────────────────────────────────
from frontend.components.sidebar import render_sidebar
render_sidebar()

from frontend.utils.localize import inject_localize

inject_localize()
