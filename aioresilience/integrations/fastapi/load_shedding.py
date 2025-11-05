"""
Load Shedding Middleware for FastAPI
"""

import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


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
    
    def __init__(self, app, load_shedder):
        """
        Initialize middleware
        
        Args:
            app: FastAPI/Starlette application
            load_shedder: LoadShedder instance from aioresilience
        """
        super().__init__(app)
        self.load_shedder = load_shedder
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through load shedder"""
        # Skip health checks and metrics endpoints
        if request.url.path in ["/health", "/metrics", "/ready", "/healthz"]:
            return await call_next(request)
        
        # Determine priority from headers
        priority = request.headers.get("X-Priority", "normal")
        
        # Try to acquire slot
        if not await self.load_shedder.acquire(priority):
            logger.warning(f"Request shed: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service temporarily overloaded. Please retry later."},
                headers={"Retry-After": "5"}
            )
        
        try:
            response = await call_next(request)
            return response
        finally:
            await self.load_shedder.release()
