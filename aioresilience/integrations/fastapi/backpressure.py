"""
Backpressure Middleware for FastAPI
"""

from typing import Callable, Optional, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE
from starlette.responses import JSONResponse

from ...logging import get_logger

logger = get_logger(__name__)


class BackpressureMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for backpressure management.
    
    Controls request flow using water marks to prevent overload.
    
    Example:
        from fastapi import FastAPI
        from aioresilience import BackpressureManager
        from aioresilience.integrations.fastapi import BackpressureMiddleware
        
        app = FastAPI()
        
        backpressure = BackpressureManager(
            max_pending=1000,
            high_water_mark=800,
            low_water_mark=200
        )
        
        app.add_middleware(BackpressureMiddleware, backpressure=backpressure)
    """
    
    def __init__(
        self,
        app,
        backpressure,
        exclude_paths: Optional[List[str]] = None,
        error_message: str = "System under backpressure",
        status_code: int = HTTP_503_SERVICE_UNAVAILABLE,
        retry_after: int = 5,
        timeout: float = 5.0,
    ):
        """
        Initialize middleware
        
        Args:
            backpressure: BackpressureManager instance
            exclude_paths: Paths to exclude
            error_message: Custom error message
            status_code: HTTP status code (default: 503)
            retry_after: Retry-After header value (default: 5)
            timeout: Timeout for acquiring backpressure slot (default: 5.0)
        """
        super().__init__(app)
        self.backpressure = backpressure
        self.exclude_paths = set(exclude_paths or ["/health", "/metrics", "/ready", "/healthz"])
        self.error_message = error_message
        self.status_code = status_code
        self.retry_after = str(retry_after)
        self.timeout = timeout
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with backpressure management"""
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Try to acquire backpressure slot
        if not await self.backpressure.acquire(timeout=self.timeout):
            logger.warning(f"Backpressure timeout: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=self.status_code,
                content={"detail": self.error_message},
                headers={"Retry-After": self.retry_after}
            )
        
        try:
            response = await call_next(request)
            return response
        finally:
            await self.backpressure.release()
