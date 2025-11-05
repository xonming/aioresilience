"""
aiohttp middleware for aioresilience patterns
"""

import logging
from typing import Optional

from aiohttp import web

from .utils import get_client_ip

logger = logging.getLogger(__name__)


def create_resilience_middleware(
    circuit_breaker=None,
    rate_limiter=None,
    rate: Optional[str] = None,
    load_shedder=None,
    timeout: Optional[float] = None,
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
    health_paths = {"/health", "/metrics", "/ready", "/healthz"}
    
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
                    {"error": f"Rate limit exceeded: {rate}"},
                    status=429,
                    headers={"Retry-After": "60"}
                )
        
        # Load shedding
        load_shed_acquired = False
        if load_shedder:
            priority = request.headers.get("X-Priority", "normal")
            if not await load_shedder.acquire(priority):
                return web.json_response(
                    {"error": "Service overloaded"},
                    status=503,
                    headers={"Retry-After": "5"}
                )
            load_shed_acquired = True
        
        try:
            # Circuit breaker check
            if circuit_breaker:
                if not await circuit_breaker.can_execute():
                    return web.json_response(
                        {
                            "error": "Service temporarily unavailable",
                            "circuit": circuit_breaker.name,
                            "state": str(circuit_breaker.get_state())
                        },
                        status=503,
                        headers={"Retry-After": str(int(circuit_breaker.recovery_timeout))}
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
