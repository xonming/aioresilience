# Sanic Integration

Resilience patterns for Sanic async applications.

Sanic is async-first, so all aioresilience patterns work natively without async/sync wrapping overhead.

## Installation

```bash
pip install aioresilience sanic
```

## Quick Start

### Using Global Setup

```python
from sanic import Sanic, json
from aioresilience import CircuitBreaker, RateLimiter, LoadShedder
from aioresilience.integrations.sanic import setup_resilience

app = Sanic("MyApp")

setup_resilience(
    app,
    circuit_breaker=CircuitBreaker(name="api"),
    rate_limiter=RateLimiter(service_name="api"),
    rate="1000/minute",
    load_shedder=LoadShedder(max_requests=500),
    timeout=30.0
)

@app.get("/api/data")
async def get_data(request):
    return json({"data": "..."})
```

### Using Decorators

```python
from sanic import Sanic, json
from aioresilience import CircuitBreaker, RateLimiter, Bulkhead
from aioresilience.integrations.sanic import (
    circuit_breaker_route,
    rate_limit_route,
    bulkhead_route,
    timeout_route,
    with_fallback_route,
)

app = Sanic("MyApp")

circuit = CircuitBreaker(name="api")
rate_limiter = RateLimiter(service_name="api")
bulkhead = Bulkhead(max_concurrent=10)

@app.get("/api/data")
@circuit_breaker_route(circuit)
@rate_limit_route(rate_limiter, "100/minute")
@bulkhead_route(bulkhead)
@timeout_route(5.0)
@with_fallback_route({"data": [], "status": "degraded"})
async def get_data(request):
    return json({"data": "..."})
```

## Available Components

- **circuit_breaker_route** - Circuit breaker decorator
- **rate_limit_route** - Rate limiting decorator
- **timeout_route** - Timeout decorator
- **bulkhead_route** - Bulkhead decorator
- **with_fallback_route** - Fallback decorator
- **setup_resilience** - Global resilience setup
- **get_client_ip** - Extract client IP with proxy support

## Why Sanic + aioresilience?

Sanic is async-native, which means:
- ✅ Zero overhead from async/sync conversion
- ✅ True async all the way down
- ✅ Maximum performance
- ✅ Natural integration with async resilience patterns
