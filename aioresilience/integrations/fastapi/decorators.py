"""
FastAPI Route Decorators for aioresilience patterns
"""

import functools
from typing import Callable, Optional, Set
from fastapi import Request, HTTPException
from starlette.responses import JSONResponse

from ...retry import RetryPolicy
from ...logging import get_logger

logger = get_logger(__name__)


def retry_route(
    retry_policy: Optional[RetryPolicy] = None,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    retry_on_status_codes: Optional[Set[int]] = None,
):
    """
    Decorator to add retry logic to FastAPI routes.
    
    Unlike RetryMiddleware, this actually retries at the route handler level.
    
    Example:
        from fastapi import FastAPI
        from aioresilience import RetryPolicy
        from aioresilience.integrations.fastapi import retry_route
        
        app = FastAPI()
        
        @app.get("/api/data")
        @retry_route(max_attempts=3)
        async def get_data():
            # This will retry up to 3 times on failure
            return {"data": "..."}
        
        # With custom policy
        policy = RetryPolicy(max_attempts=5, initial_delay=2.0)
        
        @app.get("/api/critical")
        @retry_route(retry_policy=policy)
        async def critical_endpoint():
            return {"data": "critical"}
    
    Args:
        retry_policy: Optional RetryPolicy instance
        max_attempts: Max retry attempts if no policy provided
        initial_delay: Initial delay between retries
        retry_on_status_codes: HTTP status codes to retry on
    """
    # Create policy if not provided
    if retry_policy is None:
        from ...config import RetryConfig
        retry_policy = RetryPolicy(config=RetryConfig(max_attempts=max_attempts, initial_delay=initial_delay))
    
    retry_codes = retry_on_status_codes or {500, 502, 503, 504}
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async def execute():
                try:
                    result = await func(*args, **kwargs)
                    # Check if it's a Response with a status code we should retry
                    if hasattr(result, 'status_code') and result.status_code in retry_codes:
                        raise HTTPException(status_code=result.status_code)
                    return result
                except HTTPException as e:
                    if e.status_code in retry_codes:
                        raise  # Will be retried
                    raise  # Don't retry other HTTP exceptions
            
            try:
                return await retry_policy.execute(execute)
            except Exception as e:
                logger.error(f"Route failed after {retry_policy.max_attempts} attempts: {e}")
                raise
        
        return wrapper
    return decorator
