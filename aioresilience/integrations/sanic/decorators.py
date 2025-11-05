"""
Sanic route decorators for aioresilience patterns

Since Sanic is async-first, these decorators work seamlessly with async patterns.
"""

import asyncio
import functools
from typing import Any, Callable, Optional

from sanic.response import json as sanic_json

from .utils import get_client_ip


def circuit_breaker_route(circuit_breaker):
    """
    Decorator to protect Sanic routes with circuit breaker.
    
    Example:
        from sanic import Sanic, json
        from aioresilience import CircuitBreaker
        from aioresilience.integrations.sanic import circuit_breaker_route
        
        app = Sanic("MyApp")
        circuit = CircuitBreaker(name="api", failure_threshold=5)
        
        @app.get("/api/data")
        @circuit_breaker_route(circuit)
        async def get_data(request):
            return json({"data": "..."})
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            # Check if circuit allows execution
            if not await circuit_breaker.can_execute():
                return sanic_json(
                    {
                        "error": "Service temporarily unavailable",
                        "circuit": circuit_breaker.name,
                        "state": str(circuit_breaker.get_state())
                    },
                    status=503,
                    headers={"Retry-After": str(int(circuit_breaker.recovery_timeout))}
                )
            
            try:
                # Execute the route function through circuit breaker
                result = await circuit_breaker.call(func, request, *args, **kwargs)
                return result
            except Exception as e:
                return sanic_json(
                    {"error": "Service error", "detail": str(e)},
                    status=503
                )
        
        return wrapper
    return decorator


def rate_limit_route(rate_limiter, rate: str, key_func: Optional[Callable] = None):
    """
    Decorator to apply rate limiting to Sanic routes.
    
    Example:
        from sanic import Sanic, json
        from aioresilience import RateLimiter
        from aioresilience.integrations.sanic import rate_limit_route
        
        app = Sanic("MyApp")
        rate_limiter = RateLimiter(name="api")
        
        @app.get("/api/data")
        @rate_limit_route(rate_limiter, "100/minute")
        async def get_data(request):
            return json({"data": "..."})
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            # Determine rate limit key
            if key_func:
                key = key_func(request)
            else:
                key = get_client_ip(request)
            
            # Check rate limit
            if not await rate_limiter.check_rate_limit(key, rate):
                return sanic_json(
                    {"error": f"Rate limit exceeded: {rate}"},
                    status=429,
                    headers={"Retry-After": "60"}
                )
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def timeout_route(timeout_seconds: float):
    """
    Decorator to enforce timeout on Sanic routes.
    
    Example:
        from sanic import Sanic, json
        from aioresilience.integrations.sanic import timeout_route
        
        app = Sanic("MyApp")
        
        @app.get("/api/slow")
        @timeout_route(5.0)
        async def slow_endpoint(request):
            await asyncio.sleep(10)  # Will timeout
            return json({"data": "..."})
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            try:
                result = await asyncio.wait_for(
                    func(request, *args, **kwargs),
                    timeout=timeout_seconds
                )
                return result
            except asyncio.TimeoutError:
                return sanic_json(
                    {"error": f"Request exceeded timeout of {timeout_seconds}s"},
                    status=408
                )
        
        return wrapper
    return decorator


def bulkhead_route(bulkhead):
    """
    Decorator to apply bulkhead pattern to Sanic routes.
    
    Example:
        from sanic import Sanic, json
        from aioresilience import Bulkhead
        from aioresilience.integrations.sanic import bulkhead_route
        
        app = Sanic("MyApp")
        bulkhead = Bulkhead(max_concurrent=10)
        
        @app.get("/api/data")
        @bulkhead_route(bulkhead)
        async def get_data(request):
            return json({"data": "..."})
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            try:
                result = await bulkhead.execute(func, request, *args, **kwargs)
                return result
            except Exception as e:
                return sanic_json(
                    {"error": "Service at capacity", "detail": str(e)},
                    status=503,
                    headers={"Retry-After": "10"}
                )
        
        return wrapper
    return decorator


def with_fallback_route(fallback_value: Any):
    """
    Decorator to provide fallback value for Sanic routes on error.
    
    Example:
        from sanic import Sanic, json
        from aioresilience.integrations.sanic import with_fallback_route
        
        app = Sanic("MyApp")
        
        @app.get("/api/data")
        @with_fallback_route({"data": [], "status": "degraded"})
        async def get_data(request):
            raise Exception("Service unavailable")
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            try:
                return await func(request, *args, **kwargs)
            except Exception as e:
                # Log the error
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Route failed, using fallback: {e}")
                
                # Return fallback value
                if callable(fallback_value):
                    return await fallback_value(request) if asyncio.iscoroutinefunction(fallback_value) else fallback_value(request)
                else:
                    return sanic_json(fallback_value)
        
        return wrapper
    return decorator
