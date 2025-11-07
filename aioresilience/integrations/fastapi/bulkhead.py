"""
Bulkhead Middleware for FastAPI
"""

from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE
from starlette.responses import JSONResponse

from ...logging import get_logger
from ...exceptions import BulkheadFullError, BulkheadReason

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
        
        except BulkheadFullError as e:
            # Bulkhead is full - provide rich context
            logger.warning(f"Bulkhead rejected request: {e.reason.name}")
            
            # Build detailed error response
            content = {
                "detail": str(e) if str(e) else "Service at capacity",
                "bulkhead": e.pattern_name,
                "reason": e.reason.name,
            }
            
            # Add metadata
            if e.metadata:
                content["metadata"] = {
                    "current_load": e.metadata.get("current_load"),
                    "max_concurrent": e.metadata.get("max_concurrent"),
                }
            
            # Determine retry-after based on reason
            retry_after = "10"  # default
            if e.reason == BulkheadReason.QUEUE_FULL:
                retry_after = "5"  # Queue full, retry sooner
            elif e.reason == BulkheadReason.TIMEOUT:
                retry_after = "15"  # Timeout, wait longer
            
            return JSONResponse(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                content=content,
                headers={"Retry-After": retry_after}
            )
        
        except Exception as e:
            # Other application errors
            logger.error(f"Request failed: {type(e).__name__}: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "error": str(e)}
            )
