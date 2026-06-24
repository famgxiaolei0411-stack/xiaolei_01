"""
前端常量
=========
"""

import os

# ── 后端地址（支持环境变量覆盖）───────────────────
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
API_BASE = f"{BACKEND_URL}/api/v1"

# ── 页面标题 ──────────────────────────────────────
APP_TITLE = "AI Test Copilot"
APP_SUBTITLE = "AI 驱动测试用例生成与自动化测试平台"

# ── 支持的文档格式 ────────────────────────────────
SUPPORTED_FORMATS = ["txt", "md", "docx", "pdf"]

# ── 优先级选项 ────────────────────────────────────
PRIORITY_OPTIONS = ["P0", "P1", "P2", "P3"]
PRIORITY_COLORS = {
    "P0": "🔴",
    "P1": "🟡",
    "P2": "🟢",
    "P3": "⚪",
}

# ── 测试类型选项 ──────────────────────────────────
TEST_CATEGORIES = [
    "功能测试",
    "业务规则",
    "异常场景",
    "数据测试",
    "性能测试",
    "安全测试",
    "兼容性测试",
]

# ── 用例类型选项 ──────────────────────────────────
CASE_TYPES = ["正向", "逆向", "边界"]

# ── HTTP 超时配置（秒）───────────────────────────
TIMEOUT_DEFAULT = 180       # 默认请求
TIMEOUT_AI_EXTRACT = 600    # AI 提取（功能点/测试点/用例）
TIMEOUT_AI_PIPELINE = 600   # 一键生成/自动化管线
TIMEOUT_RAG_INDEX = 300     # RAG 索引构建
TIMEOUT_RAG_SEARCH = 120    # RAG 语义检索
TIMEOUT_TEST_RUN = 600      # 测试执行


# ── 安全取值工具 ────────────────────────────────────
def safe_get(data: dict, *keys, default=None):
    """链式安全取值，任一步为 None/非 dict 时返回 default。

    Usage:
        safe_get(result, "data", "features", default=[])
    """
    for key in keys:
        if not isinstance(data, dict):
            return default
        data = data.get(key)
        if data is None:
            return default
    return data
