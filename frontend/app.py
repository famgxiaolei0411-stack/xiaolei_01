"""
AI Test Copilot — Streamlit 主入口
=====================================
多页面应用配置与全局路由。

启动方式:
    streamlit run frontend/app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from frontend.components.sidebar import render_sidebar
from frontend.utils.constants import APP_TITLE, APP_SUBTITLE
from frontend.utils.localize import inject_localize
from frontend.utils.session import init_session

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session()
render_sidebar()

st.markdown(
    """
<style>
.main .block-container {
    max-width: 1120px;
    padding-top: 4.2rem;
}
.hero-title {
    font-size: 48px;
    line-height: 1.12;
    font-weight: 800;
    color: #262b3a;
    margin: 0 0 10px 0;
}
.hero-subtitle {
    font-size: 19px;
    line-height: 1.7;
    color: #586174;
    max-width: 760px;
    margin-bottom: 22px;
}
.status-panel {
    border: 1px solid #d8dee9;
    border-radius: 8px;
    padding: 18px 20px;
    background: #fbfcfe;
    margin: 24px 0 12px 0;
}
.status-label {
    font-size: 13px;
    color: #70798b;
    margin-bottom: 5px;
}
.status-value {
    font-size: 18px;
    font-weight: 700;
    color: #2b3040;
}
.flow-card {
    border: 1px solid #dfe4ec;
    border-radius: 8px;
    padding: 16px 18px;
    min-height: 142px;
    background: #ffffff;
}
.flow-index {
    font-size: 13px;
    font-weight: 700;
    color: #62708a;
    margin-bottom: 10px;
}
.flow-title {
    font-size: 18px;
    font-weight: 800;
    color: #2b3040;
    margin-bottom: 8px;
}
.flow-copy {
    font-size: 14px;
    color: #5f687a;
    line-height: 1.6;
}
.feature-list {
    border-left: 3px solid #4f7cff;
    padding-left: 16px;
    color: #3c4352;
    line-height: 1.9;
}
.small-note {
    color: #737d90;
    font-size: 13px;
}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
<div class="hero-title">🧪 {APP_TITLE}</div>
<div class="hero-subtitle">{APP_SUBTITLE}。上传需求文档或接口文档后，系统会自动识别文档类型，并按对应场景生成测试点、测试用例和可导出的结果文件。</div>
""",
    unsafe_allow_html=True,
)

project_id = st.session_state.get("project_id")
project_name = st.session_state.get("project_name", "")
project_status = st.session_state.get("project_status", "")
status_map = {
    "created": "已创建项目",
    "parsed": "已上传并解析文档",
    "features_extracted": "已提取功能点",
    "testpoints_generated": "已生成测试点",
    "testcases_generated": "已生成测试用例",
    "exported": "已导出结果文件",
}

if project_id:
    status_text = status_map.get(project_status, project_status or "待处理")
    st.markdown(
        f"""
<div class="status-panel">
  <div class="status-label">当前项目</div>
  <div class="status-value">{project_name} <span class="small-note">ID: {project_id} · {status_text}</span></div>
</div>
""",
        unsafe_allow_html=True,
    )
else:
    st.info("请先在左侧进入「上传文档」页面，创建或选择一个项目。")

st.markdown("---")
st.markdown("## 工作流程")

steps = [
    ("01", "上传文档", "支持 TXT、Markdown、DOCX、PDF。系统会自动识别需求文档或接口文档。"),
    ("02", "提取功能点", "从文档中抽取业务模块、功能点、前置条件和关键规则。"),
    ("03", "生成测试点", "围绕功能、异常、边界、安全等维度生成可评审的测试点。"),
    ("04", "生成测试用例", "根据文档类型自动选择功能测试或接口测试的用例结构。"),
    ("05", "导出结果", "导出 Excel、JSON 或 Markdown，便于评审、交付和沉淀。"),
]

for row_start in range(0, len(steps), 3):
    cols = st.columns(3)
    for col, item in zip(cols, steps[row_start:row_start + 3]):
        idx, title, copy = item
        with col:
            st.markdown(
                f"""
<div class="flow-card">
  <div class="flow-index">{idx}</div>
  <div class="flow-title">{title}</div>
  <div class="flow-copy">{copy}</div>
</div>
""",
                unsafe_allow_html=True,
            )

st.markdown("## 当前能力")
left, right = st.columns([1.2, 1])
with left:
    st.markdown(
        """
<div class="feature-list">
<strong>自动识别文档类型</strong>：不需要手动选择功能文档或接口文档。<br>
<strong>支持人工校正</strong>：功能点、测试点、测试用例都可以编辑。<br>
<strong>质量评审</strong>：生成用例后会给出评分、问题和建议。<br>
<strong>本地运行</strong>：SQLite 保存数据，适合个人电脑和开源部署。
</div>
""",
        unsafe_allow_html=True,
    )
with right:
    st.markdown(
        """
<div class="status-panel">
  <div class="status-label">建议下一步</div>
  <div class="status-value">上传一份需求文档</div>
  <div class="small-note">进入「上传文档」页面后，可以单步生成，也可以直接一键生成完整结果。</div>
</div>
""",
        unsafe_allow_html=True,
    )

st.markdown("---")
st.caption("AI Test Copilot v2.0.0 | 本地测试用例生成与评审工具")

inject_localize()
