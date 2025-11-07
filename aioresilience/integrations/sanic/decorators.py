"""
Sanic route decorators for aioresilience patterns

Since Sanic is async-first, these decorators work seamlessly with async patterns.
"""

import asyncio
import functools
from typing import Any, Callable, Optional

from sanic.response import json as sanic_json

from .utils import get_client_ip


def circuit_breaker_route(
    circuit_breaker,
    error_message: str = "Service temporarily unavailable",
    status_code: int = 503,
    retry_after: Optional[int] = None,
    include_info: bool = True,
):
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
                content = {"error": error_message}
                if include_info:
                    content["circuit"] = circuit_breaker.name
                    content["state"] = str(circuit_breaker.get_state())
                
                return sanic_json(
                    content,
                    status=status_code,
                    headers={"Retry-After": str(retry_after if retry_after is not None else int(circuit_breaker.recovery_timeout))}
                )
            
            try:
                # Execute the route function through circuit breaker
                result = await circuit_breaker.call(func, request, *args, **kwargs)
                return result
            except Exception as e:
                return sanic_json(
                    {"error": "Service error", "detail": str(e)},
                    status=status_code
                )
        
        return wrapper
    return decorator


def rate_limit_route(
    rate_limiter,
    rate: str,
    key_func: Optional[Callable] = None,
    error_message: str = "Rate limit exceeded",
    status_code: int = 429,
    retry_after: int = 60,
):
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
                    {"error": f"{error_message}: {rate}"},
                    status=status_code,
                    headers={"Retry-After": str(retry_after)}
                )
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def timeout_route(
    timeout_seconds: float,
    error_message: str = "Request exceeded timeout",
    status_code: int = 408,
):
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
                    {"error": f"{error_message} of {timeout_seconds}s"},
                    status=status_code
                )
        
        return wrapper
    return decorator


def bulkhead_route(
    bulkhead,
    error_message: str = "Service at capacity",
    status_code: int = 503,
    retry_after: int = 10,
):
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
                    {"error": error_message, "detail": str(e)},
                    status=status_code,
                    headers={"Retry-After": str(retry_after)}
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
                from ...logging import get_logger
                logger = get_logger(__name__)
                logger.error(f"Route failed, using fallback: {e}")
                
                # Return fallback value
                if callable(fallback_value):
                    return await fallback_value(request) if asyncio.iscoroutinefunction(fallback_value) else fallback_value(request)
                else:
                    return sanic_json(fallback_value)
        
        return wrapper
    return decorator


def backpressure_route(
    backpressure,
    timeout: float = 5.0,
    error_message: str = "System under backpressure",
    status_code: int = 503,
    retry_after: int = 5,
):
    """
    Decorator to apply backpressure management to Sanic routes.
    
    Example:
        from sanic import Sanic, json
        from aioresilience import BackpressureManager
        from aioresilience.integrations.sanic import backpressure_route
        
        app = Sanic("MyApp")
        bp = BackpressureManager(max_pending=1000)
        
        @app.get("/api/data")
        @backpressure_route(bp)
        async def get_data(request):
            return json({"data": "..."})
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            if not await backpressure.acquire(timeout=timeout):
                return sanic_json(
                    {"error": error_message},
                    status=status_code,
                    headers={"Retry-After": str(retry_after)}
                )
            
            try:
                return await func(request, *args, **kwargs)
            finally:
                await backpressure.release()
        
        return wrapper
    return decorator


def adaptive_concurrency_route(
    limiter,
    error_message: str = "Concurrency limit reached",
    status_code: int = 503,
    retry_after: int = 1,
):
    """
    Decorator to apply adaptive concurrency limiting to Sanic routes.
    
    Example:
        from sanic import Sanic, json
        from aioresilience import AdaptiveConcurrencyLimiter
        from aioresilience.config import AdaptiveConcurrencyConfig
        from aioresilience.integrations.sanic import adaptive_concurrency_route

        app = Sanic("MyApp")
        config = AdaptiveConcurrencyConfig(initial_limit=100)
        limiter = AdaptiveConcurrencyLimiter("api-limiter", config)

        @app.get("/api/data")
        @adaptive_concurrency_route(limiter)
        async def get_data(request):
            return json({"data": "..."})
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            if not await limiter.acquire():
                return sanic_json(
                    {"error": error_message},
                    status=status_code,
                    headers={"Retry-After": str(retry_after)}
                )
            
            success = False
            try:
                result = await func(request, *args, **kwargs)
                success = True
                return result
            finally:
                await limiter.release(success=success)
        
        return wrapper
    return decorator
