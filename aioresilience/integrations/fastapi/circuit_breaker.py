"""FastAPI CircuitBreaker Middleware"""

import asyncio
from typing import Callable, Optional, Dict, List
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE
from starlette.responses import JSONResponse

from ...logging import get_logger

logger = get_logger(__name__)


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
        exclude_paths: Optional[List[str]] = None,
        error_message: str = "Service temporarily unavailable due to circuit breaker",
        error_detail_factory: Optional[Callable] = None,
        status_code: int = HTTP_503_SERVICE_UNAVAILABLE,
        retry_after: Optional[int] = None,
        include_circuit_info: bool = True,
        response_factory: Optional[Callable] = None,
    ):
        """
        Initialize middleware
        
        Args:
            circuit_breaker: CircuitBreaker instance
            exclude_paths: Paths to exclude from circuit breaker (e.g., health checks)
            error_message: Custom error message for circuit open state
            error_detail_factory: Optional callable(circuit_breaker) -> dict for custom error details
            status_code: HTTP status code for circuit open responses (default: 503)
            retry_after: Retry-After header value in seconds (default: uses circuit.recovery_timeout)
            include_circuit_info: Include circuit name and state in response (default: True)
            response_factory: Optional callable(circuit_breaker, request) -> Response for full control
        """
        super().__init__(app)
        self.circuit_breaker = circuit_breaker
        
        # Performance: Convert to set for O(1) lookup instead of O(n)
        self.exclude_paths = set(exclude_paths or ["/health", "/metrics", "/ready", "/healthz"])
        
        # Configurable response parameters
        self.error_message = error_message
        self.error_detail_factory = error_detail_factory
        self.status_code = status_code
        self.retry_after = retry_after
        self.include_circuit_info = include_circuit_info
        self.response_factory = response_factory
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through circuit breaker"""
        # Skip excluded paths (O(1) set lookup)
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # Check if circuit breaker allows execution
        if not await self.circuit_breaker.can_execute():
            # Conditional logging
            if logger.isEnabledFor(30):  # WARNING level
                logger.warning(f"Circuit breaker OPEN for '{request.url.path}'")
            
            # Use custom response factory if provided
            if self.response_factory:
                return self.response_factory(self.circuit_breaker, request)
            
            # Build response content
            if self.error_detail_factory:
                content = self.error_detail_factory(self.circuit_breaker)
            else:
                content = {"detail": self.error_message}
                if self.include_circuit_info:
                    content["circuit"] = self.circuit_breaker.name
                    content["state"] = str(self.circuit_breaker.get_state())
            
            # Determine Retry-After value
            retry_after_value = str(
                self.retry_after if self.retry_after is not None 
                else int(self.circuit_breaker.recovery_timeout)
            )
            
            return JSONResponse(
                status_code=self.status_code,
                content=content,
                headers={"Retry-After": retry_after_value}
            )
        
        try:
            # Execute request through circuit breaker
            async def execute_request():
                return await call_next(request)
            
            return await self.circuit_breaker.call(execute_request)
        except Exception as e:
            # Circuit breaker already recorded the failure
            logger.error(f"Request failed through circuit breaker: {e}")
            return JSONResponse(
                status_code=self.status_code,
                content={"detail": "Service error", "error": str(e)}
            )
