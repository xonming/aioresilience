"""
FastAPI dependency injection utilities for aioresilience patterns
"""

from fastapi import HTTPException, Request
from starlette.status import HTTP_429_TOO_MANY_REQUESTS
from typing import Optional, Callable

from .utils import get_client_ip


def rate_limit_dependency(
    rate_limiter,
    rate: str,
    error_message: str = "Rate limit exceeded",
    status_code: int = HTTP_429_TOO_MANY_REQUESTS,
    retry_after: int = 60,
    key_func: Optional[Callable[[Request], str]] = None,
):
    """
    Create FastAPI dependency for rate limiting.
    
    Uses client IP address as the rate limit key by default.
    
    Example:
        from fastapi import FastAPI, Depends
        from aioresilience import RateLimiter
        from aioresilience.integrations.fastapi import rate_limit_dependency
        
        app = FastAPI()
        rate_limiter = RateLimiter(name="my_service")
        
        @app.get("/api/data", dependencies=[Depends(rate_limit_dependency(rate_limiter, "100/minute"))])
        async def get_data():
            return {"data": "..."}
    
    Args:
        rate_limiter: RateLimiter instance
        rate: Rate limit string (e.g., "100/minute")
        error_message: Custom error message (default: "Rate limit exceeded")
        status_code: HTTP status code (default: 429)
        retry_after: Retry-After header value in seconds (default: 60)
        key_func: Optional function to extract rate limit key from request (default: client IP)
    
    Returns:
        FastAPI dependency function
    """
    async def check_rate_limit(request: Request):
        """Check rate limit for the current request"""
        # Use custom key function or default to client IP
        key = key_func(request) if key_func else get_client_ip(request)
        
        if not await rate_limiter.check_rate_limit(key, rate):
            raise HTTPException(
                status_code=status_code,
                detail=f"{error_message}: {rate}",
                headers={"Retry-After": str(retry_after)}
            )
    
    return check_rate_limit
