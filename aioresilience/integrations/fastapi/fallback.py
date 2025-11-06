"""
Fallback Middleware for FastAPI
"""

import asyncio
from typing import Callable, Optional, Any, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ...logging import get_logger

logger = get_logger(__name__)


class FallbackMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for providing fallback responses on errors.
    
    Returns fallback response when the request handler raises an exception.
    
    Example:
        from fastapi import FastAPI
        from aioresilience.integrations.fastapi import FallbackMiddleware
        
        app = FastAPI()
        
        # Simple fallback
        app.add_middleware(
            FallbackMiddleware,
            fallback_response={"status": "degraded", "data": []}
        )
        
        # Or with factory
        def create_fallback(request, exc):
            return JSONResponse({"error": str(exc)}, status_code=503)
        
        app.add_middleware(FallbackMiddleware, fallback_factory=create_fallback)
    """
    
    def __init__(
        self,
        app,
        fallback_response: Optional[Any] = None,
        fallback_factory: Optional[Callable] = None,
        exclude_paths: Optional[List[str]] = None,
        catch_exceptions: tuple = (Exception,),
        status_code: int = 200,
        log_errors: bool = True,
    ):
        """
        Initialize middleware
        
        Args:
            fallback_response: Static fallback response (dict will be JSON)
            fallback_factory: Callable(request, exception) -> Response for dynamic fallbacks
            exclude_paths: Paths to exclude from fallback handling
            catch_exceptions: Tuple of exception types to catch (default: all Exception)
            status_code: HTTP status code for fallback responses (default: 200)
            log_errors: Whether to log errors before returning fallback (default: True)
        """
        super().__init__(app)
        
        if fallback_response is None and fallback_factory is None:
            raise ValueError("Either fallback_response or fallback_factory must be provided")
        
        self.fallback_response = fallback_response
        self.fallback_factory = fallback_factory
        self.exclude_paths = set(exclude_paths or [])
        self.catch_exceptions = catch_exceptions
        self.status_code = status_code
        self.log_errors = log_errors
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with fallback protection"""
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        try:
            return await call_next(request)
        except self.catch_exceptions as e:
            if self.log_errors:
                logger.error(f"Request failed, using fallback: {request.method} {request.url.path}: {e}")
            
            # Use factory if provided
            if self.fallback_factory:
                result = self.fallback_factory(request, e)
                if asyncio.iscoroutine(result):
                    return await result
                return result
            
            # Use static fallback
            if isinstance(self.fallback_response, Response):
                return self.fallback_response
            else:
                return JSONResponse(
                    content=self.fallback_response,
                    status_code=self.status_code
                )
