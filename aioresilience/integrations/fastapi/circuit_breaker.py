"""
Circuit Breaker Middleware for FastAPI
"""

import logging
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class CircuitBreakerMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for circuit breaker pattern.
    
    Protects backend services by failing fast when error thresholds are exceeded.
    
    Example:
        from fastapi import FastAPI
        from aioresilience import CircuitBreaker
        from aioresilience.integrations.fastapi import CircuitBreakerMiddleware
        
        app = FastAPI()
        circuit = CircuitBreaker(
            name="backend",
            failure_threshold=5,
            recovery_timeout=60.0
        )
        
        app.add_middleware(CircuitBreakerMiddleware, circuit_breaker=circuit)
    """
    
    def __init__(
        self,
        app,
        circuit_breaker,
        exclude_paths: Optional[list[str]] = None
    ):
        """
        Initialize middleware
        
        Args:
            app: FastAPI/Starlette application
            circuit_breaker: CircuitBreaker instance
            exclude_paths: Paths to exclude from circuit breaker (e.g., health checks)
        """
        super().__init__(app)
        self.circuit_breaker = circuit_breaker
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/ready", "/healthz"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through circuit breaker"""
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Check if circuit breaker allows execution
        if not await self.circuit_breaker.can_execute():
            logger.warning(f"Circuit breaker OPEN for {request.url.path}")
            return JSONResponse(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "detail": "Service temporarily unavailable due to circuit breaker",
                    "circuit": self.circuit_breaker.name,
                    "state": str(self.circuit_breaker.get_state())
                },
                headers={"Retry-After": str(int(self.circuit_breaker.recovery_timeout))}
            )
        
        try:
            response = await self.circuit_breaker.call(call_next, request)
            return response
        except Exception as e:
            # Circuit breaker already recorded the failure
            logger.error(f"Request failed through circuit breaker: {e}")
            return JSONResponse(
                status_code=HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Service error", "error": str(e)}
            )
