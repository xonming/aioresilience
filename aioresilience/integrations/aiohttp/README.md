# aiohttp Integration

Resilience patterns for aiohttp async applications.

aiohttp is async-first, so all aioresilience patterns work natively without async/sync wrapping overhead.

## Installation

```bash
pip install aioresilience aiohttp
```

## Quick Start

### Using Middleware

```python
from aiohttp import web
from aioresilience import CircuitBreaker, RateLimiter, LoadShedder
from aioresilience.integrations.aiohttp import create_resilience_middleware

app = web.Application()

app.middlewares.append(create_resilience_middleware(
    circuit_breaker=CircuitBreaker(name="api"),
    rate_limiter=RateLimiter(service_name="api"),
    rate="1000/minute",
    load_shedder=LoadShedder(max_requests=500),
    timeout=30.0
))

async def get_data(request):
    return web.json_response({"data": "..."})

app.router.add_get("/api/data", get_data)

web.run_app(app)
```

### Using Decorators

```python
from aiohttp import web
from aioresilience import CircuitBreaker, RateLimiter, Bulkhead
from aioresilience.integrations.aiohttp import (
    circuit_breaker_handler,
    rate_limit_handler,
    bulkhead_handler,
    timeout_handler,
    with_fallback_handler,
)

circuit = CircuitBreaker(name="api")
rate_limiter = RateLimiter(service_name="api")
bulkhead = Bulkhead(max_concurrent=10)

@circuit_breaker_handler(circuit)
@rate_limit_handler(rate_limiter, "100/minute")
@bulkhead_handler(bulkhead)
@timeout_handler(5.0)
@with_fallback_handler({"data": [], "status": "degraded"})
async def get_data(request):
    return web.json_response({"data": "..."})

app = web.Application()
app.router.add_get("/api/data", get_data)

web.run_app(app)
```

## Available Components

- **circuit_breaker_handler** - Circuit breaker decorator
- **rate_limit_handler** - Rate limiting decorator
- **timeout_handler** - Timeout decorator
- **bulkhead_handler** - Bulkhead decorator
- **with_fallback_handler** - Fallback decorator
- **create_resilience_middleware** - Middleware factory
- **get_client_ip** - Extract client IP with proxy support

## Why aiohttp + aioresilience?

aiohttp is async-native, which means:
- ✅ Zero overhead from async/sync conversion
- ✅ True async all the way down
- ✅ Maximum performance
- ✅ Natural integration with async resilience patterns
- ✅ Clean middleware architecture
