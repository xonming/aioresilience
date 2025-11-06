"""
aiohttp handler decorators for aioresilience patterns
"""

import asyncio
import functools
from typing import Any, Callable, Optional

from aiohttp import web

from .utils import get_client_ip


def circuit_breaker_handler(
    circuit_breaker,
    error_message: str = "Service temporarily unavailable",
    status_code: int = 503,
    retry_after: Optional[int] = None,
    include_info: bool = True,
):
    """
    Decorator to protect aiohttp handlers with circuit breaker.
    
    Example:
        from aiohttp import web
        from aioresilience import CircuitBreaker
        from aioresilience.integrations.aiohttp import circuit_breaker_handler
        
        circuit = CircuitBreaker(name="api", failure_threshold=5)
        
        @circuit_breaker_handler(circuit)
        async def get_data(request):
            return web.json_response({"data": "..."})
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
                
                return web.json_response(
                    content,
                    status=status_code,
                    headers={"Retry-After": str(retry_after if retry_after is not None else int(circuit_breaker.recovery_timeout))}
                )
            
            try:
                # Execute the handler function through circuit breaker
                result = await circuit_breaker.call(func, request, *args, **kwargs)
                return result
            except Exception as e:
                return web.json_response(
                    {"error": "Service error", "detail": str(e)},
                    status=status_code
                )
        
        return wrapper
    return decorator


def rate_limit_handler(
    rate_limiter,
    rate: str,
    key_func: Optional[Callable] = None,
    error_message: str = "Rate limit exceeded",
    status_code: int = 429,
    retry_after: int = 60,
):
    """
    Decorator to apply rate limiting to aiohttp handlers.
    
    Example:
        from aiohttp import web
        from aioresilience import RateLimiter
        from aioresilience.integrations.aiohttp import rate_limit_handler
        
        rate_limiter = RateLimiter(name="api")
        
        @rate_limit_handler(rate_limiter, "100/minute")
        async def get_data(request):
            return web.json_response({"data": "..."})
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
                return web.json_response(
                    {"error": f"{error_message}: {rate}"},
                    status=status_code,
                    headers={"Retry-After": str(retry_after)}
                )
            
            return await func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def timeout_handler(
    timeout_seconds: float,
    error_message: str = "Request exceeded timeout",
    status_code: int = 408,
):
    """
    Decorator to enforce timeout on aiohttp handlers.
    
    Example:
        from aiohttp import web
        from aioresilience.integrations.aiohttp import timeout_handler
        
        @timeout_handler(5.0)
        async def slow_endpoint(request):
            await asyncio.sleep(10)  # Will timeout
            return web.json_response({"data": "..."})
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
                return web.json_response(
                    {"error": f"{error_message} of {timeout_seconds}s"},
                    status=status_code
                )
        
        return wrapper
    return decorator


def bulkhead_handler(
    bulkhead,
    error_message: str = "Service at capacity",
    status_code: int = 503,
    retry_after: int = 10,
):
    """
    Decorator to apply bulkhead pattern to aiohttp handlers.
    
    Example:
        from aiohttp import web
        from aioresilience import Bulkhead
        from aioresilience.integrations.aiohttp import bulkhead_handler
        
        bulkhead = Bulkhead(max_concurrent=10)
        
        @bulkhead_handler(bulkhead)
        async def get_data(request):
            return web.json_response({"data": "..."})
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            try:
                result = await bulkhead.execute(func, request, *args, **kwargs)
                return result
            except Exception as e:
                return web.json_response(
                    {"error": error_message, "detail": str(e)},
                    status=status_code,
                    headers={"Retry-After": str(retry_after)}
                )
        
        return wrapper
    return decorator


def with_fallback_handler(fallback_value: Any):
    """
    Decorator to provide fallback value for aiohttp handlers on error.
    
    Example:
        from aiohttp import web
        from aioresilience.integrations.aiohttp import with_fallback_handler
        
        @with_fallback_handler({"data": [], "status": "degraded"})
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
                logger.error(f"Handler failed, using fallback: {e}")
                
                # Return fallback value
                if callable(fallback_value):
                    if asyncio.iscoroutinefunction(fallback_value):
                        return await fallback_value(request)
                    else:
                        return fallback_value(request)
                else:
                    return web.json_response(fallback_value)
        
        return wrapper
    return decorator


def backpressure_handler(
    backpressure,
    timeout: float = 5.0,
    error_message: str = "System under backpressure",
    status_code: int = 503,
    retry_after: int = 5,
):
    """
    Decorator to apply backpressure management to aiohttp handlers.
    
    Example:
        from aiohttp import web
        from aioresilience import BackpressureManager
        from aioresilience.integrations.aiohttp import backpressure_handler
        
        bp = BackpressureManager(max_pending=1000)
        
        @backpressure_handler(bp)
        async def get_data(request):
            return web.json_response({"data": "..."})
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            if not await backpressure.acquire(timeout=timeout):
                return web.json_response(
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


def adaptive_concurrency_handler(
    limiter,
    error_message: str = "Concurrency limit reached",
    status_code: int = 503,
    retry_after: int = 1,
):
    """
    Decorator to apply adaptive concurrency limiting to aiohttp handlers.
    
    Example:
        from aiohttp import web
        from aioresilience import AdaptiveConcurrencyLimiter
        from aioresilience.integrations.aiohttp import adaptive_concurrency_handler
        
        limiter = AdaptiveConcurrencyLimiter(initial_limit=100)
        
        @adaptive_concurrency_handler(limiter)
        async def get_data(request):
            return web.json_response({"data": "..."})
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(request, *args, **kwargs):
            if not await limiter.acquire():
                return web.json_response(
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
