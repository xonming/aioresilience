"""
aiohttp middleware for aioresilience patterns
"""

from typing import Optional, Set

from aiohttp import web

from ...logging import get_logger
from .utils import get_client_ip

logger = get_logger(__name__)


def create_resilience_middleware(
    circuit_breaker=None,
    rate_limiter=None,
    rate: Optional[str] = None,
    load_shedder=None,
    timeout: Optional[float] = None,
    # Configurability
    exclude_paths: Optional[Set[str]] = None,
    circuit_error_message: str = "Service temporarily unavailable",
    circuit_status_code: int = 503,
    circuit_retry_after: Optional[int] = None,
    circuit_include_info: bool = True,
    rate_error_message: str = "Rate limit exceeded",
    rate_status_code: int = 429,
    rate_retry_after: int = 60,
    load_error_message: str = "Service overloaded",
    load_status_code: int = 503,
    load_retry_after: int = 5,
    priority_header: str = "X-Priority",
    default_priority: str = "normal",
):
    """
    Create aiohttp middleware with resilience patterns.
    
    Example:
        from aiohttp import web
        from aioresilience import CircuitBreaker, RateLimiter, LoadShedder
        from aioresilience.integrations.aiohttp import create_resilience_middleware
        
        app = web.Application()
        
        app.middlewares.append(create_resilience_middleware(
            circuit_breaker=CircuitBreaker(name="api"),
            rate_limiter=RateLimiter(name="api"),
            rate="1000/minute",
            load_shedder=LoadShedder(max_requests=500),
            timeout=30.0
        ))
    
    Args:
        circuit_breaker: Optional CircuitBreaker instance
        rate_limiter: Optional RateLimiter instance
        rate: Rate limit string (required if rate_limiter is provided)
        load_shedder: Optional LoadShedder instance
        timeout: Optional global timeout in seconds
    
    Returns:
        aiohttp middleware function
    """
    # Performance: Convert to set for O(1) lookup
    health_paths = exclude_paths or {"/health", "/metrics", "/ready", "/healthz"}
    
    @web.middleware
    async def resilience_middleware(request, handler):
        """Apply resilience patterns to requests"""
        # Skip health checks
        if request.path in health_paths:
            return await handler(request)
        
        # Rate limiting
        if rate_limiter and rate:
            client_ip = get_client_ip(request)
            if not await rate_limiter.check_rate_limit(client_ip, rate):
                return web.json_response(
                    {"error": f"{rate_error_message}: {rate}"},
                    status=rate_status_code,
                    headers={"Retry-After": str(rate_retry_after)}
                )
        
        # Load shedding
        load_shed_acquired = False
        if load_shedder:
            priority = request.headers.get(priority_header, default_priority)
            if not await load_shedder.acquire(priority):
                return web.json_response(
                    {"error": load_error_message},
                    status=load_status_code,
                    headers={"Retry-After": str(load_retry_after)}
                )
            load_shed_acquired = True
        
        try:
            # Circuit breaker check
            if circuit_breaker:
                if not await circuit_breaker.can_execute():
                    content = {"error": circuit_error_message}
                    if circuit_include_info:
                        content["circuit"] = circuit_breaker.name
                        content["state"] = str(circuit_breaker.get_state())
                    
                    return web.json_response(
                        content,
                        status=circuit_status_code,
                        headers={"Retry-After": str(circuit_retry_after if circuit_retry_after is not None else int(circuit_breaker.recovery_timeout))}
                    )
            
            # Execute handler
            if timeout:
                import asyncio
                try:
                    response = await asyncio.wait_for(
                        handler(request),
                        timeout=timeout
                    )
                    return response
                except asyncio.TimeoutError:
                    return web.json_response(
                        {"error": f"Request exceeded timeout of {timeout}s"},
                        status=408
                    )
            else:
                response = await handler(request)
                return response
        
        finally:
            # Release load shedder if it was acquired
            if load_shed_acquired:
                await load_shedder.release()
    
    logger.info("Resilience middleware configured for aiohttp app")
    return resilience_middleware
