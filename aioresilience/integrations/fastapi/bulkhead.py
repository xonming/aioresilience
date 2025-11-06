"""
Bulkhead Middleware for FastAPI
"""

from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE
from starlette.responses import JSONResponse

from ...logging import get_logger

logger = get_logger(__name__)


class BulkheadMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for bulkhead pattern.
    
    Limits concurrent requests to prevent resource exhaustion.
    
    Example:
        from fastapi import FastAPI
        from aioresilience import Bulkhead
        from aioresilience.integrations.fastapi import BulkheadMiddleware
        
        app = FastAPI()
        bulkhead = Bulkhead(
            max_concurrent=100,
            max_waiting=50,
            timeout=5.0
        )
        
        app.add_middleware(BulkheadMiddleware, bulkhead=bulkhead)
    """
    
    def __init__(
        self,
        app,
        bulkhead,
        exclude_paths: Optional[list[str]] = None
    ):
        """
        Initialize middleware
        
        Args:
            app: FastAPI/Starlette application
            bulkhead: Bulkhead instance
            exclude_paths: Paths to exclude from bulkhead
        """
        super().__init__(app)
        self.bulkhead = bulkhead
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/ready", "/healthz"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through bulkhead"""
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        try:
            async with self.bulkhead:
                response = await call_next(request)
                return response
        except Exception as e:
            # Bulkhead full or other error
            logger.warning(f"Bulkhead rejected request: '{request.url.path}'")
            return JSONResponse(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "detail": "Service at capacity. Please retry later.",
                    "error": str(e)
                },
                headers={"Retry-After": "10"}
            )
