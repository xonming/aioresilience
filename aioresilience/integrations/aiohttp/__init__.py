"""
aiohttp Integration for aioresilience

Provides middleware and decorators for integrating resilience patterns
with aiohttp async applications.

aiohttp is async-first, so all resilience patterns work natively without wrapping.

Example:
    from aiohttp import web
    from aioresilience import CircuitBreaker, RateLimiter
    from aioresilience.integrations.aiohttp import (
        circuit_breaker_handler,
        rate_limit_handler,
        create_resilience_middleware,
    )
    
    app = web.Application()
    circuit = CircuitBreaker(name="api")
    rate_limiter = RateLimiter(name="api")
    
    # Add middleware
    app.middlewares.append(create_resilience_middleware(
        circuit_breaker=circuit,
        rate_limiter=rate_limiter,
        rate="1000/minute"
    ))
    
    # Or use decorators
    @circuit_breaker_handler(circuit)
    @rate_limit_handler(rate_limiter, "100/minute")
    async def get_data(request):
        return web.json_response({"data": "..."})
    
    app.router.add_get("/api/data", get_data)
"""

from .decorators import (
    circuit_breaker_handler,
    rate_limit_handler,
    timeout_handler,
    bulkhead_handler,
    with_fallback_handler,
)
from .middleware import create_resilience_middleware
from .utils import get_client_ip

__all__ = [
    # Decorators
    "circuit_breaker_handler",
    "rate_limit_handler",
    "timeout_handler",
    "bulkhead_handler",
    "with_fallback_handler",
    # Middleware
    "create_resilience_middleware",
    # Utilities
    "get_client_ip",
]
