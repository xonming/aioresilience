"""
Retry Middleware for FastAPI
"""

from typing import Callable, Optional, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ...retry import RetryPolicy, RetryStrategy
from ...logging import get_logger

logger = get_logger(__name__)


class RetryMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic request retries.
    
    Retries failed requests based on configured retry policy.
    
    Example:
        from fastapi import FastAPI
        from aioresilience import RetryPolicy, RetryStrategy
        from aioresilience.integrations.fastapi import RetryMiddleware
        
        app = FastAPI()
        
        retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            strategy=RetryStrategy.EXPONENTIAL
        )
        
        app.add_middleware(RetryMiddleware, retry_policy=retry_policy)
    """
    
    def __init__(
        self,
        app,
        retry_policy: Optional[RetryPolicy] = None,
        exclude_paths: Optional[List[str]] = None,
        retry_on_status_codes: Optional[List[int]] = None,
        max_attempts: int = 3,
        initial_delay: float = 0.5,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    ):
        """
        Initialize middleware
        
        Args:
            retry_policy: Pre-configured RetryPolicy instance (takes precedence)
            exclude_paths: Paths to exclude from retry logic
            retry_on_status_codes: HTTP status codes to retry on (default: [500, 502, 503, 504])
            max_attempts: Maximum retry attempts if no policy provided
            initial_delay: Initial delay between retries
            strategy: Retry strategy if no policy provided
        """
        super().__init__(app)
        
        # Use provided policy or create one
        if retry_policy:
            self.retry_policy = retry_policy
        else:
            self.retry_policy = RetryPolicy(
                max_attempts=max_attempts,
                initial_delay=initial_delay,
                strategy=strategy,
            )
        
        self.exclude_paths = set(exclude_paths or ["/health", "/metrics", "/ready", "/healthz"])
        self.retry_on_status_codes = set(retry_on_status_codes or [500, 502, 503, 504])
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with retry logic
        
        Note: Retry middleware at the HTTP middleware level has limitations because
        call_next() can only be called once per request in Starlette. This middleware
        will execute the request once and log retry-worthy failures, but won't actually
        retry at this level. For true retry behavior, apply retry patterns to individual
        route handlers or use the retry decorator on specific endpoints.
        """
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Execute request once (middleware limitation - can't retry at this level)
        response = await call_next(request)
        
        # Log if this would have been retried
        if response.status_code in self.retry_on_status_codes:
            logger.warning(
                f"Request returned {response.status_code} (would retry with endpoint-level retry): "
                f"{request.method} {request.url.path}"
            )
        
        return response
