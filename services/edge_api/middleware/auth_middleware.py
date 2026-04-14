"""Request logging middleware for audit trail."""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = logging.getLogger(__name__)

EXEMPT_PATHS = {"/health", "/auth/login", "/docs", "/openapi.json", "/redoc"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        start = time.time()
        response = await call_next(request)
        duration = time.time() - start

        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration * 1000, 2),
            },
        )
        return response
