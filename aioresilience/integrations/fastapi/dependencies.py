"""
FastAPI dependency injection utilities for aioresilience patterns
"""

from fastapi import HTTPException, Request
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from .utils import get_client_ip


def rate_limit_dependency(rate_limiter, rate: str):
    """
    Create FastAPI dependency for rate limiting.
    
    Usage:
        from fastapi import FastAPI, Depends
        from aioresilience import RateLimiter
        from aioresilience.integrations.fastapi import rate_limit_dependency
        
        app = FastAPI()
        rate_limiter = RateLimiter(name="my_service")
        
        @app.get("/api/data", dependencies=[Depends(rate_limit_dependency(rate_limiter, "100/minute"))])
        async def get_data():
            return {"data": "..."}
    
    Args:
        rate_limiter: RateLimiter instance (LocalRateLimiter or RedisRateLimiter)
        rate: Rate limit string (e.g., "100/minute")
        
    Returns:
        FastAPI dependency function
    """
    async def check_rate_limit(request: Request):
        """Check rate limit for the current request"""
        client_ip = get_client_ip(request)
        
        if not await rate_limiter.check_rate_limit(client_ip, rate):
            raise HTTPException(
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: {rate}",
                headers={"Retry-After": "60"}
            )
    
    return check_rate_limit
