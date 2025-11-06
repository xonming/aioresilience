"""
Load Shedding Middleware for FastAPI
"""

from typing import Callable, Optional, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE
from starlette.responses import JSONResponse

from ...logging import get_logger

logger = get_logger(__name__)


class LoadSheddingMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for load shedding
    
    Automatically rejects requests when system is overloaded.
    
    Example:
        from fastapi import FastAPI
        from aioresilience import LoadShedder
        from aioresilience.integrations.fastapi import LoadSheddingMiddleware
        
        app = FastAPI()
        load_shedder = LoadShedder(
            max_requests=1000,
            cpu_threshold=85.0,
            memory_threshold=85.0
        )
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
    """
    
    def __init__(
        self,
        app,
        load_shedder,
        exclude_paths: Optional[List[str]] = None,
        error_message: str = "Service temporarily overloaded. Please retry later.",
        status_code: int = HTTP_503_SERVICE_UNAVAILABLE,
        retry_after: int = 5,
        priority_header: str = "X-Priority",
        default_priority: str = "normal",
        response_factory: Optional[Callable] = None,
    ):
        """
        Initialize middleware
        
        Args:
            load_shedder: LoadShedder instance
            exclude_paths: Paths to exclude from load shedding
            error_message: Custom error message
            status_code: HTTP status code (default: 503)
            retry_after: Retry-After header value in seconds (default: 5)
            priority_header: Header name for priority (default: "X-Priority")
            default_priority: Default priority if header not present (default: "normal")
            response_factory: Optional callable(load_shedder, request) -> Response
        """
        super().__init__(app)
        self.load_shedder = load_shedder
        
        # Performance: Convert to set for O(1) lookup
        self.exclude_paths = set(exclude_paths or ["/health", "/metrics", "/ready", "/healthz"])
        
        # Configurable parameters
        self.error_message = error_message
        self.status_code = status_code
        self.retry_after = str(retry_after)
        self.priority_header = priority_header
        self.default_priority = default_priority
        self.response_factory = response_factory
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through load shedder"""
        # Skip excluded paths (O(1) set lookup)
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Get priority from request
        priority = request.headers.get(self.priority_header, self.default_priority)
        
        # Try to acquire slot
        if not await self.load_shedder.acquire(priority):
            logger.warning(f"Request shed: {request.method} {request.url.path}")
            
            # Use custom response factory if provided
            if self.response_factory:
                return self.response_factory(self.load_shedder, request)
            
            return JSONResponse(
                status_code=self.status_code,
                content={"detail": self.error_message},
                headers={"Retry-After": self.retry_after}
            )
        
        try:
            # Execute request
            response = await call_next(request)
            return response
        finally:
            # Always release the slot
            await self.load_shedder.release()
