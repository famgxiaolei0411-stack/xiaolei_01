"""
AI Test Copilot — 全局配置
============================
集中管理所有配置项：路径、API Key、模型参数、分块策略等。
"""

import os
import logging
from pathlib import Path
from dotenv import load_dotenv

# ── 项目根目录 ──────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent

# ── 加载 .env 文件 ──────────────────────────────────────
load_dotenv(PROJECT_ROOT / ".env", override=True)

# ── 安全解析工具 ──────────────────────────────────────
_log = logging.getLogger(__name__)


def _int(key: str, default: int) -> int:
    """安全解析 int 环境变量，解析失败时返回默认值并告警。"""
    val = os.getenv(key, str(default))
    try:
        return int(val)
    except (ValueError, TypeError):
        _log.warning("配置 [%s]=%r 不是有效整数，使用默认值 %d", key, val, default)
        return default


def _float(key: str, default: float) -> float:
    """安全解析 float 环境变量。"""
    val = os.getenv(key, str(default))
    try:
        return float(val)
    except (ValueError, TypeError):
        _log.warning("配置 [%s]=%r 不是有效浮点数，使用默认值 %.2f", key, val, default)
        return default


# ══════════════════════════════════════════════════════════
# AI 模型配置（支持多 Provider 切换）
# ══════════════════════════════════════════════════════════
# AI_PROVIDER: deepseek | openai
# 设为 openai 则使用 OpenAI/GPT 模型，需填 OPENAI_API_KEY
# 设为 deepseek 则使用 DeepSeek 模型（默认，性价比高）
AI_PROVIDER = os.getenv("AI_PROVIDER", "deepseek")

# DeepSeek 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# OpenAI 配置（兼容 Azure、本地 Ollama 等 OpenAI 兼容服务）
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

PLACEHOLDER_API_KEYS = {
    "",
    "sk-your-api-key-here",
    "sk-your-openai-key-here",
}


def is_configured_api_key(api_key: str | None) -> bool:
    """判断 API Key 是否为可用配置值。"""
    return bool(api_key and api_key.strip() not in PLACEHOLDER_API_KEYS)


def get_ai_config_status() -> dict:
    """返回 AI 配置状态，不暴露密钥内容。"""
    provider = AI_PROVIDER
    if provider == "openai":
        api_key = OPENAI_API_KEY
        model = OPENAI_MODEL
    else:
        provider = "deepseek"
        api_key = DEEPSEEK_API_KEY
        model = DEEPSEEK_MODEL

    configured = is_configured_api_key(api_key)
    return {
        "provider": provider,
        "model": model,
        "configured": configured,
    }

# 通用参数
AI_MAX_TOKENS = _int("AI_MAX_TOKENS", 4096)
AI_TEMPERATURE = _float("AI_TEMPERATURE", 0.3)
AI_TIMEOUT = _int("AI_TIMEOUT", 120)
AI_MAX_RETRIES = _int("AI_MAX_RETRIES", 3)

# ══════════════════════════════════════════════════════════
# 文档分块策略
# ══════════════════════════════════════════════════════════
CHUNK_SIZE = _int("CHUNK_SIZE", 3000)      # 每个 chunk 的字符数
CHUNK_OVERLAP = _int("CHUNK_OVERLAP", 300) # 相邻 chunk 的重叠字符数

# ══════════════════════════════════════════════════════════
# 路径配置
# ══════════════════════════════════════════════════════════
UPLOAD_DIR = PROJECT_ROOT / os.getenv("UPLOAD_DIR", "uploads")
OUTPUT_DIR = PROJECT_ROOT / os.getenv("OUTPUT_DIR", "outputs")
PROMPT_DIR = PROJECT_ROOT / "prompts"

# 确保目录存在
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════
# 数据库配置
# ══════════════════════════════════════════════════════════
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite+aiosqlite:///{PROJECT_ROOT / 'aitest.db'}"
)
DATABASE_URL_SYNC = os.getenv(
    "DATABASE_URL_SYNC",
    f"sqlite:///{PROJECT_ROOT / 'aitest.db'}"
)

# ══════════════════════════════════════════════════════════
# 后端服务配置
# ══════════════════════════════════════════════════════════
BACKEND_HOST = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT = _int("BACKEND_PORT", 8000)
BACKEND_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"

# ══════════════════════════════════════════════════════════
# 文件上传限制
# ══════════════════════════════════════════════════════════
MAX_UPLOAD_SIZE_MB = _int("MAX_UPLOAD_SIZE_MB", 10)

# ══════════════════════════════════════════════════════════
# SQLite 连接池
# ══════════════════════════════════════════════════════════
DB_POOL_SIZE = _int("DB_POOL_SIZE", 5)
DB_POOL_RECYCLE = _int("DB_POOL_RECYCLE", 3600)

# ══════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════
# Streamlit 配置
# ══════════════════════════════════════════════════════════
STREAMLIT_PORT = _int("STREAMLIT_PORT", 8501)

# ══════════════════════════════════════════════════════════
# 支持的文档格式
# ══════════════════════════════════════════════════════════
SUPPORTED_EXTENSIONS = {".txt", ".md", ".docx", ".pdf"}

# ══════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════

# Pytest 执行参数

# ══════════════════════════════════════════════════════════
