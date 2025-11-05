"""
Sanic middleware setup for aioresilience
"""

import logging
from typing import Optional

from sanic.response import json as sanic_json

from .utils import get_client_ip

logger = logging.getLogger(__name__)


def setup_resilience(
    app,
    circuit_breaker=None,
    rate_limiter=None,
    rate: Optional[str] = None,
    load_shedder=None,
    timeout: Optional[float] = None,
):
    """
    Setup global resilience patterns for a Sanic application.
    
    This configures middleware to apply resilience patterns to all routes.
    
    Example:
        from sanic import Sanic
        from aioresilience import CircuitBreaker, RateLimiter, LoadShedder
        from aioresilience.integrations.sanic import setup_resilience
        
        app = Sanic("MyApp")
        
        setup_resilience(
            app,
            circuit_breaker=CircuitBreaker(name="api"),
            rate_limiter=RateLimiter(name="api"),
            rate="1000/minute",
            load_shedder=LoadShedder(max_requests=500),
            timeout=30.0
        )
    
    Args:
        app: Sanic application instance
        circuit_breaker: Optional CircuitBreaker instance
        rate_limiter: Optional RateLimiter instance
        rate: Rate limit string (required if rate_limiter is provided)
        load_shedder: Optional LoadShedder instance
        timeout: Optional global timeout in seconds
    """
    health_paths = {"/health", "/metrics", "/ready", "/healthz"}
    
    @app.middleware("request")
    async def apply_resilience(request):
        """Apply resilience patterns before each request"""
        # Skip health checks
        if request.path in health_paths:
            return None
        
        # Rate limiting
        if rate_limiter and rate:
            client_ip = get_client_ip(request)
            if not await rate_limiter.check_rate_limit(client_ip, rate):
                return sanic_json(
                    {"error": f"Rate limit exceeded: {rate}"},
                    status=429,
                    headers={"Retry-After": "60"}
                )
        
        # Load shedding
        if load_shedder:
            priority = request.headers.get("X-Priority", "normal")
            if not await load_shedder.acquire(priority):
                # Mark that we didn't acquire
                request.ctx.load_shed_acquired = False
                return sanic_json(
                    {"error": "Service overloaded"},
                    status=503,
                    headers={"Retry-After": "5"}
                )
            request.ctx.load_shed_acquired = True
        
        # Circuit breaker check
        if circuit_breaker:
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
        
        return None
    
    @app.middleware("response")
    async def cleanup_resilience(request, response):
        """Cleanup resilience patterns after each request"""
        # Release load shedder if it was acquired
        if load_shedder and hasattr(request.ctx, "load_shed_acquired") and request.ctx.load_shed_acquired:
            await load_shedder.release()
        
        return response
    
    logger.info("Resilience patterns configured for Sanic app")
