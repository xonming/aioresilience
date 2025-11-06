"""
Sanic middleware setup for aioresilience
"""

from typing import Optional, Set

from sanic.response import json as sanic_json
from sanic.response import text
from sanic import Sanic, Request, HTTPResponse

from ...logging import get_logger
from .utils import get_client_ip

logger = get_logger(__name__)


def setup_resilience(
    app,
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
        exclude_paths: Paths to exclude from resilience patterns
        circuit_error_message: Custom circuit breaker error message
        circuit_status_code: HTTP status code for circuit breaker (default: 503)
        circuit_retry_after: Retry-After header for circuit (default: uses recovery_timeout)
        circuit_include_info: Include circuit name and state in response
        rate_error_message: Custom rate limit error message
        rate_status_code: HTTP status code for rate limit (default: 429)
        rate_retry_after: Retry-After header for rate limit (default: 60)
        load_error_message: Custom load shedding error message
        load_status_code: HTTP status code for load shedding (default: 503)
        load_retry_after: Retry-After header for load shedding (default: 5)
        priority_header: Header name for priority (default: "X-Priority")
        default_priority: Default priority value (default: "normal")
    """
    # Performance: Convert to set for O(1) lookup
    health_paths = exclude_paths or {"/health", "/metrics", "/ready", "/healthz"}
    
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
                    {"error": f"{rate_error_message}: {rate}"},
                    status=rate_status_code,
                    headers={"Retry-After": str(rate_retry_after)}
                )
        
        # Load shedding
        if load_shedder:
            priority = request.headers.get(priority_header, default_priority)
            if not await load_shedder.acquire(priority):
                # Mark that we didn't acquire
                request.ctx.load_shed_acquired = False
                return sanic_json(
                    {"error": load_error_message},
                    status=load_status_code,
                    headers={"Retry-After": str(load_retry_after)}
                )
            request.ctx.load_shed_acquired = True
        
        # Circuit breaker check
        if circuit_breaker:
            if not await circuit_breaker.can_execute():
                content = {"error": circuit_error_message}
                if circuit_include_info:
                    content["circuit"] = circuit_breaker.name
                    content["state"] = str(circuit_breaker.get_state())
                
                retry_after_value = str(
                    circuit_retry_after if circuit_retry_after is not None
                    else int(circuit_breaker.recovery_timeout)
                )
                
                return sanic_json(
                    content,
                    status=circuit_status_code,
                    headers={"Retry-After": retry_after_value}
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
