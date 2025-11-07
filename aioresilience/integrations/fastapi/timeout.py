"""
Timeout Middleware for FastAPI
"""

import asyncio
from typing import Callable, Optional, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_408_REQUEST_TIMEOUT
from starlette.responses import JSONResponse
from ...timeout import TimeoutManager
from ...logging import get_logger
from ...exceptions import OperationTimeoutError, TimeoutReason

logger = get_logger(__name__)


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
        exclude_paths: Optional[List[str]] = None,
        error_message: str = "Request exceeded timeout",
        status_code: int = HTTP_408_REQUEST_TIMEOUT,
        response_factory: Optional[Callable] = None,
    ):
        """
        Initialize middleware
        
        Args:
            app: FastAPI/Starlette application
            timeout: Request timeout in seconds
            exclude_paths: Paths to exclude from timeout
            error_message: Custom error message
            status_code: HTTP status code (default: 408)
            response_factory: Optional callable(timeout, request, elapsed) -> Response
        """
        super().__init__(app)
        self.timeout = timeout
        self.exclude_paths = set(exclude_paths or [])
        self.error_message = error_message
        self.status_code = status_code
        self.response_factory = response_factory
    
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
            
            if self.response_factory:
                return self.response_factory(self.timeout, request, self.timeout)
            
            return JSONResponse(
                status_code=self.status_code,
                content={"detail": f"{self.error_message} of {self.timeout}s"}
            )
