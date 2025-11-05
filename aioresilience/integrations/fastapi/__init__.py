"""
FastAPI / Starlette Integration for aioresilience

Provides middleware and dependencies for integrating resilience patterns
with FastAPI applications.

Available Middleware:
- LoadSheddingMiddleware: Reject requests under high load
- CircuitBreakerMiddleware: Fail fast when error thresholds exceeded
- TimeoutMiddleware: Enforce request timeouts
- BulkheadMiddleware: Limit concurrent requests
- ResilienceMiddleware: Composite middleware combining multiple patterns

Available Dependencies:
- rate_limit_dependency: FastAPI dependency for rate limiting

Utilities:
- get_client_ip: Extract client IP with proxy support

Example:
    from fastapi import FastAPI
    from aioresilience import LoadShedder, CircuitBreaker
    from aioresilience.integrations.fastapi import (
        LoadSheddingMiddleware,
        CircuitBreakerMiddleware,
        ResilienceMiddleware,
    )
    
    app = FastAPI()
    
    # Add individual middlewares
    app.add_middleware(LoadSheddingMiddleware, load_shedder=LoadShedder(max_requests=1000))
    app.add_middleware(CircuitBreakerMiddleware, circuit_breaker=CircuitBreaker(name="backend"))
    
    # Or use composite middleware
    app.add_middleware(
        ResilienceMiddleware,
        rate_limiter=RateLimiter(name="api"),
        rate="1000/minute",
        load_shedder=LoadShedder(max_requests=500),
        timeout=30.0
    )
"""

from .load_shedding import LoadSheddingMiddleware
from .circuit_breaker import CircuitBreakerMiddleware
from .timeout import TimeoutMiddleware
from .bulkhead import BulkheadMiddleware
from .composite import ResilienceMiddleware
from .dependencies import rate_limit_dependency
from .utils import get_client_ip

__all__ = [
    # Middleware
    "LoadSheddingMiddleware",
    "CircuitBreakerMiddleware",
    "TimeoutMiddleware",
    "BulkheadMiddleware",
    "ResilienceMiddleware",
    # Dependencies
    "rate_limit_dependency",
    # Utilities
    "get_client_ip",
]
