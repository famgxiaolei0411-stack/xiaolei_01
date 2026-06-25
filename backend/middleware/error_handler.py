"""
全局异常处理中间件
====================
统一捕获并格式化所有未处理异常。
"""

import logging
import re

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.db.crud import update_project_status
from backend.db.database import async_session_factory

logger = logging.getLogger(__name__)


class GlobalErrorHandler(BaseHTTPMiddleware):
    """全局异常处理中间件。

    捕获路由中未处理的异常，返回统一的 JSON 错误响应。
    避免将内部错误详情直接暴露给前端。
    """

    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.exception(
                "未处理异常 [%s %s]: %s",
                request.method,
                request.url.path,
                exc,
            )
            await _restore_project_status(request.url.path)
            # 不暴露内部异常详情，只返回通用错误消息
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "message": "服务器内部错误，请稍后重试",
                    "detail": "如果问题持续，请联系管理员",
                },
            )


async def _restore_project_status(path: str) -> None:
    """生成接口异常后恢复项目状态，避免卡在处理中。"""
    status_by_suffix = {
        "/features/extract": "parsed",
        "/testpoints/generate": "features_extracted",
        "/testcases/generate": "testpoints_generated",
        "/auto-generate": "parsed",
    }
    fallback_status = next(
        (status for suffix, status in status_by_suffix.items() if path.endswith(suffix)),
        None,
    )
    if not fallback_status:
        return

    match = re.match(r"^/api/v1/projects/(\d+)/", path)
    if not match:
        return

    project_id = int(match.group(1))
    try:
        async with async_session_factory() as session:
            await update_project_status(session, project_id, fallback_status)
            await session.commit()
    except Exception:
        logger.exception("恢复项目状态失败: project_id=%d, status=%s", project_id, fallback_status)
