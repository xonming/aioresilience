"""
Timeout Middleware for FastAPI
"""

import asyncio
import logging
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_408_REQUEST_TIMEOUT
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class TimeoutMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for request timeouts.
    
    Enforces maximum execution time for requests.
    
    Example:
        from fastapi import FastAPI
        from aioresilience.integrations.fastapi import TimeoutMiddleware
        
        app = FastAPI()
        app.add_middleware(TimeoutMiddleware, timeout=30.0)
    """
    
    def __init__(
        self,
        app,
        timeout: float = 30.0,
        exclude_paths: Optional[list[str]] = None
    ):
        """
        Initialize middleware
        
        Args:
            app: FastAPI/Starlette application
            timeout: Request timeout in seconds
            exclude_paths: Paths to exclude from timeout
        """
        super().__init__(app)
        self.timeout = timeout
        self.exclude_paths = exclude_paths or []
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with timeout"""
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        try:
            response = await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout
            )
            return response
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout: {request.method} {request.url.path}")
            return JSONResponse(
                status_code=HTTP_408_REQUEST_TIMEOUT,
                content={
                    "detail": f"Request exceeded timeout of {self.timeout}s"
                }
            )
