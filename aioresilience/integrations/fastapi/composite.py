"""
Composite Resilience Middleware for FastAPI

Combines multiple resilience patterns into a single middleware.
"""

import asyncio
import logging
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import (
    HTTP_503_SERVICE_UNAVAILABLE,
    HTTP_429_TOO_MANY_REQUESTS,
    HTTP_408_REQUEST_TIMEOUT,
)
from starlette.responses import JSONResponse

from .utils import get_client_ip

logger = logging.getLogger(__name__)


class ResilienceMiddleware(BaseHTTPMiddleware):
    """
    Composite middleware combining multiple resilience patterns.
    
    Applies resilience patterns in the following order:
    1. Rate limiting (per-client)
    2. Load shedding (global)
    3. Bulkhead (resource isolation)
    4. Circuit breaker (failure protection)
    5. Timeout (time bounds)
    
    Example:
        from fastapi import FastAPI
        from aioresilience import (
            RateLimiter, LoadShedder, Bulkhead,
            CircuitBreaker
        )
        from aioresilience.integrations.fastapi import ResilienceMiddleware
        
        app = FastAPI()
        
        app.add_middleware(
            ResilienceMiddleware,
            rate_limiter=RateLimiter(name="api"),
            rate="1000/minute",
            load_shedder=LoadShedder(max_requests=500),
            bulkhead=Bulkhead(max_concurrent=100),
            circuit_breaker=CircuitBreaker(name="backend"),
            timeout=30.0
        )
    """
    
    def __init__(
        self,
        app,
        rate_limiter=None,
        rate: Optional[str] = None,
        load_shedder=None,
        bulkhead=None,
        circuit_breaker=None,
        timeout: Optional[float] = None,
        exclude_paths: Optional[list[str]] = None
    ):
        """
        Initialize composite middleware
        
        Args:
            app: FastAPI/Starlette application
            rate_limiter: Optional RateLimiter instance
            rate: Rate limit string (e.g., "100/minute")
            load_shedder: Optional LoadShedder instance
            bulkhead: Optional Bulkhead instance
            circuit_breaker: Optional CircuitBreaker instance
            timeout: Optional request timeout in seconds
            exclude_paths: Paths to exclude from resilience patterns
        """
        super().__init__(app)
        self.rate_limiter = rate_limiter
        self.rate = rate
        self.load_shedder = load_shedder
        self.bulkhead = bulkhead
        self.circuit_breaker = circuit_breaker
        self.timeout_seconds = timeout
        self.exclude_paths = exclude_paths or ["/health", "/metrics", "/ready", "/healthz"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through all configured resilience patterns"""
        if request.url.path in self.exclude_paths:
            return await call_next(request)
        
        # 1. Rate limiting (per-client)
        if self.rate_limiter and self.rate:
            client_ip = get_client_ip(request)
            if not await self.rate_limiter.check_rate_limit(client_ip, self.rate):
                return JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": f"Rate limit exceeded: {self.rate}"},
                    headers={"Retry-After": "60"}
                )
        
        # 2. Load shedding (global)
        if self.load_shedder:
            priority = request.headers.get("X-Priority", "normal")
            if not await self.load_shedder.acquire(priority):
                return JSONResponse(
                    status_code=HTTP_503_SERVICE_UNAVAILABLE,
                    content={"detail": "Service overloaded"},
                    headers={"Retry-After": "5"}
                )
        
        try:
            # 3. Bulkhead (resource isolation)
            if self.bulkhead:
                await self.bulkhead._try_acquire()
                bulkhead_acquired = True
            else:
                bulkhead_acquired = False
            
            try:
                # 4. Circuit breaker (failure protection)
                async def execute_request():
                    # 5. Timeout (time bounds)
                    if self.timeout_seconds:
                        return await asyncio.wait_for(
                            call_next(request),
                            timeout=self.timeout_seconds
                        )
                    else:
                        return await call_next(request)
                
                if self.circuit_breaker:
                    if not await self.circuit_breaker.can_execute():
                        return JSONResponse(
                            status_code=HTTP_503_SERVICE_UNAVAILABLE,
                            content={"detail": "Circuit breaker open"},
                            headers={"Retry-After": "30"}
                        )
                    response = await self.circuit_breaker.call(execute_request)
                else:
                    response = await execute_request()
                
                return response
            
            except asyncio.TimeoutError:
                return JSONResponse(
                    status_code=HTTP_408_REQUEST_TIMEOUT,
                    content={"detail": f"Request timeout ({self.timeout_seconds}s)"}
                )
            finally:
                if bulkhead_acquired:
                    self.bulkhead._semaphore.release()
        
        finally:
            if self.load_shedder:
                await self.load_shedder.release()
