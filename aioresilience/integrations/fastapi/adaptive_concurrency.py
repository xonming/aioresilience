"""
Adaptive Concurrency Middleware for FastAPI
"""

from typing import Callable, Optional, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE
from starlette.responses import JSONResponse

from ...logging import get_logger

logger = get_logger(__name__)


class AdaptiveConcurrencyMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for adaptive concurrency limiting.
    
    Automatically adjusts concurrency limits based on success rate using AIMD algorithm.
    
    Example:
        from fastapi import FastAPI
        from aioresilience import AdaptiveConcurrencyLimiter
        from aioresilience.config import AdaptiveConcurrencyConfig
        from aioresilience.integrations.fastapi import AdaptiveConcurrencyMiddleware
        
        app = FastAPI()
        
        config = AdaptiveConcurrencyConfig(initial_limit=100)
        limiter = AdaptiveConcurrencyLimiter("api-limiter", config)
        
        app.add_middleware(AdaptiveConcurrencyMiddleware, limiter=limiter)
    """
    
    def __init__(
        self,
        app,
        limiter,
        exclude_paths: Optional[List[str]] = None,
        error_message: str = "Concurrency limit reached",
        status_code: int = HTTP_503_SERVICE_UNAVAILABLE,
        retry_after: int = 1,
    ):
        """
        Initialize middleware
        
        Args:
            limiter: AdaptiveConcurrencyLimiter instance
            exclude_paths: Paths to exclude
            error_message: Custom error message
            status_code: HTTP status code (default: 503)
            retry_after: Retry-After header value (default: 1)
        """
        super().__init__(app)
        self.limiter = limiter
        self.exclude_paths = set(exclude_paths or ["/health", "/metrics", "/ready", "/healthz"])
        self.error_message = error_message
        self.status_code = status_code
        self.retry_after = str(retry_after)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with adaptive concurrency limiting"""
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Try to acquire concurrency slot
        if not await self.limiter.acquire():
            logger.warning(f"Concurrency limit reached: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=self.status_code,
                content={"detail": self.error_message},
                headers={"Retry-After": self.retry_after}
            )
        
        success = False
        try:
            response = await call_next(request)
            # Consider 2xx and 3xx as success
            success = 200 <= response.status_code < 400
            return response
        except Exception:
            success = False
            raise
        finally:
            await self.limiter.release(success=success)
