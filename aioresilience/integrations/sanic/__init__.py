"""
Sanic Integration for aioresilience

Provides middleware and decorators for integrating resilience patterns
with Sanic async applications.

Sanic is async-first, so all resilience patterns work natively without wrapping.

Example:
    from sanic import Sanic, json
    from aioresilience import CircuitBreaker, RateLimiter
    from aioresilience.integrations.sanic import (
        circuit_breaker_route,
        rate_limit_route,
        setup_resilience,
    )
    
    app = Sanic("MyApp")
    circuit = CircuitBreaker(name="api")
    rate_limiter = RateLimiter(name="api")
    
    # Global setup
    setup_resilience(app, circuit_breaker=circuit, rate_limiter=rate_limiter, rate="1000/minute")
    
    # Or use decorators
    @app.get("/api/data")
    @circuit_breaker_route(circuit)
    @rate_limit_route(rate_limiter, "100/minute")
    async def get_data(request):
        return json({"data": "..."})
"""

from .decorators import (
    circuit_breaker_route,
    rate_limit_route,
    timeout_route,
    bulkhead_route,
    with_fallback_route,
)
from .middleware import setup_resilience
from .utils import get_client_ip

__all__ = [
    # Decorators
    "circuit_breaker_route",
    "rate_limit_route",
    "timeout_route",
    "bulkhead_route",
    "with_fallback_route",
    # Setup
    "setup_resilience",
    # Utilities
    "get_client_ip",
]
