"""
全局异常处理中间件
====================
统一捕获并格式化所有未处理异常。
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

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
            # 不暴露内部异常详情，只返回通用错误消息
            return JSONResponse(
                status_code=500,
                content={
                    "ok": False,
                    "message": "服务器内部错误，请稍后重试",
                    "detail": "如果问题持续，请联系管理员",
                },
            )
