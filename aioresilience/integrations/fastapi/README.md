# FastAPI Integration - Modular Architecture

This package provides middleware and dependency injection utilities for integrating **aioresilience** resilience patterns with FastAPI applications.

## Architecture

The FastAPI integration is organized into modular components for better maintainability and clarity:

```
fastapi/
├── __init__.py           # Package exports and documentation
├── utils.py              # Utility functions (get_client_ip, etc.)
├── dependencies.py       # FastAPI dependency injection utilities
├── load_shedding.py      # LoadSheddingMiddleware
├── circuit_breaker.py    # CircuitBreakerMiddleware
├── timeout.py            # TimeoutMiddleware
├── bulkhead.py           # BulkheadMiddleware
├── composite.py          # ResilienceMiddleware (combines multiple patterns)
└── README.md             # This file
```

## Available Components

### Middleware

#### LoadSheddingMiddleware
Rejects requests when the system is overloaded based on request count or system metrics.

```python
from fastapi import FastAPI
from aioresilience import LoadShedder
from aioresilience.integrations.fastapi import LoadSheddingMiddleware

app = FastAPI()
load_shedder = LoadShedder(max_requests=1000)
app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
```

#### CircuitBreakerMiddleware
Protects backend services by failing fast when error thresholds are exceeded.

```python
from aioresilience import CircuitBreaker
from aioresilience.integrations.fastapi import CircuitBreakerMiddleware

circuit = CircuitBreaker(name="backend", failure_threshold=5)
app.add_middleware(CircuitBreakerMiddleware, circuit_breaker=circuit)
```

#### TimeoutMiddleware
Enforces maximum execution time for requests.

```python
from aioresilience.integrations.fastapi import TimeoutMiddleware

app.add_middleware(TimeoutMiddleware, timeout=30.0)
```

#### BulkheadMiddleware
Limits concurrent requests to prevent resource exhaustion.

```python
from aioresilience import Bulkhead
from aioresilience.integrations.fastapi import BulkheadMiddleware

bulkhead = Bulkhead(max_concurrent=100, max_waiting=50)
app.add_middleware(BulkheadMiddleware, bulkhead=bulkhead)
```

#### ResilienceMiddleware (Composite)
Combines multiple resilience patterns into a single middleware.

```python
from aioresilience import RateLimiter, LoadShedder, Bulkhead, CircuitBreaker
from aioresilience.integrations.fastapi import ResilienceMiddleware

app.add_middleware(
    ResilienceMiddleware,
    rate_limiter=RateLimiter(service_name="api"),
    rate="1000/minute",
    load_shedder=LoadShedder(max_requests=500),
    bulkhead=Bulkhead(max_concurrent=100),
    circuit_breaker=CircuitBreaker(name="backend"),
    timeout=30.0
)
```

### Route Decorators

#### retry_route (Recommended for Retry Logic)
Route-level decorator for applying retry logic to specific endpoints.

```python
from aioresilience import RetryPolicy
from aioresilience.integrations.fastapi import retry_route

@app.get("/api/data")
@retry_route(RetryPolicy(max_attempts=3, initial_delay=0.1, exponential_base=2))
async def get_data():
    # This will retry up to 3 times with exponential backoff
    return {"data": "..."}
```

**Note:** Use `retry_route` decorator instead of `RetryMiddleware` for retry logic. 
`RetryMiddleware` has limitations due to Starlette's `call_next()` behavior, which 
consumes the response stream and prevents true retries. The `retry_route` decorator 
properly retries at the route level.

### Dependencies

#### rate_limit_dependency
FastAPI dependency for applying rate limits to specific endpoints.

```python
from fastapi import Depends
from aioresilience import RateLimiter
from aioresilience.integrations.fastapi import rate_limit_dependency

rate_limiter = RateLimiter(service_name="api")

@app.get("/api/data", dependencies=[Depends(rate_limit_dependency(rate_limiter, "100/minute"))])
async def get_data():
    return {"data": "..."}
```

### Utilities

#### get_client_ip
Extracts client IP address with proxy support (X-Forwarded-For, X-Real-IP).

```python
from aioresilience.integrations.fastapi import get_client_ip

@app.get("/info")
async def get_info(request: Request):
    client_ip = get_client_ip(request)
    return {"client_ip": client_ip}
```

## Design Principles

1. **Modularity**: Each resilience pattern is in its own module
2. **Independence**: Middleware can be used individually or combined
3. **Composability**: ResilienceMiddleware allows layering multiple patterns
4. **Consistency**: All middleware follow the same structure and patterns
5. **Observability**: Proper logging and error messages throughout

## Middleware Execution Order

When using ResilienceMiddleware, patterns are applied in this order:

1. **Rate Limiting** - Per-client request rate control
2. **Load Shedding** - Global overload protection
3. **Bulkhead** - Resource isolation and concurrency limits
4. **Circuit Breaker** - Failure detection and fast-fail
5. **Timeout** - Time-bound request execution

This order ensures that:
- Expensive operations (like circuit breaker calls) happen after cheap checks (rate limiting)
- Resource limits (bulkhead) are enforced before potentially slow operations
- Timeouts apply to the entire request chain

## Health Check Exclusions

Most middleware automatically excludes common health check endpoints:
- `/health`
- `/metrics`
- `/ready`
- `/healthz`

You can customize excluded paths using the `exclude_paths` parameter.

## Migration from Monolithic fastapi.py

The previous monolithic `fastapi.py` has been refactored into this modular structure. All imports remain backward compatible:

```python
# Still works the same way
from aioresilience.integrations.fastapi import (
    LoadSheddingMiddleware,
    CircuitBreakerMiddleware,
    # ... etc
)
```

## Contributing

When adding new middleware:
1. Create a new file in this directory
2. Follow the existing middleware structure
3. Add to `__init__.py` exports
4. Update this README
5. Add tests in `tests/test_fastapi_integration.py`
