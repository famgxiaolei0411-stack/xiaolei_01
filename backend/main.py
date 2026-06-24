"""
AI Test Copilot — FastAPI 应用入口
=====================================
组装所有路由、中间件、数据库生命周期。

启动方式:
    uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
"""

import logging
import time
from collections import defaultdict

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api import documents, features, testpoints, testcases, export, automation
from backend.db.database import init_db, close_db
from backend.middleware.error_handler import GlobalErrorHandler
from config import BACKEND_HOST, BACKEND_PORT

# ── 日志配置 ──────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── 简易限流器（30次/分钟/IP）──────────────────────
RATE_LIMIT = 100     # 请求次数（前端单页加载会发多个请求）
RATE_WINDOW = 60     # 时间窗口（秒）
_rate_store: dict[str, list[float]] = defaultdict(list)

# ── FastAPI 应用实例 ──────────────────────────────
app = FastAPI(
    title="AI Test Copilot",
    description="AI 驱动测试用例生成与自动化测试平台",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── 简易限流中间件 ──────────────────────────────
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """每个 IP 每分钟最多 30 次请求。"""
    # 跳过健康检查和文档页面的限流
    if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()

    # 清理过期记录
    _rate_store[client_ip] = [
        t for t in _rate_store[client_ip] if now - t < RATE_WINDOW
    ]

    if len(_rate_store[client_ip]) >= RATE_LIMIT:
        logger.warning("限流触发: IP=%s, 请求=%d/min", client_ip, len(_rate_store[client_ip]))
        return JSONResponse(
            status_code=429,
            content={
                "ok": False,
                "message": "请求过于频繁，请稍后重试",
                "detail": f"每分钟最多 {RATE_LIMIT} 次请求",
            },
        )

    _rate_store[client_ip].append(now)
    return await call_next(request)

# ── CORS 配置（允许 Streamlit 前端跨域访问）────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 全局异常处理 ──────────────────────────────────
app.add_middleware(GlobalErrorHandler)


# ── 生命周期事件 ──────────────────────────────────
@app.on_event("startup")
async def on_startup() -> None:
    """应用启动：初始化数据库、验证配置。"""
    logger.info("=" * 50)
    logger.info("AI Test Copilot 启动中...")
    logger.info("=" * 50)

    # 初始化数据库表
    await init_db()
    logger.info("✓ 数据库初始化完成")

    logger.info("✓ API 文档: http://%s:%d/docs", BACKEND_HOST, BACKEND_PORT)
    logger.info("=" * 50)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    """应用关闭：释放数据库连接。"""
    logger.info("AI Test Copilot 正在关闭...")
    await close_db()
    logger.info("✓ 数据库连接已释放")


# ── 注册路由 ──────────────────────────────────────
app.include_router(documents.router)
app.include_router(features.router)
app.include_router(testpoints.router)
app.include_router(testcases.router)
app.include_router(export.router)
app.include_router(automation.router)


# ── 健康检查 ──────────────────────────────────────
@app.get("/health", tags=["系统"])
async def health_check() -> dict:
    """健康检查端点。

    Returns:
        服务状态
    """
    return {
        "status": "ok",
        "service": "AI Test Copilot",
        "version": "2.0.0",
    }


# ── 直接启动入口 ──────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        reload=True,
        log_level="info",
    )
