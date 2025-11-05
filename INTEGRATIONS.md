# Framework Integrations Guide

**aioresilience** provides seamless integrations with major async Python web frameworks.

## 📦 Available Integrations

| Framework | Status | Type | Performance |
|-----------|--------|------|-------------|
| **FastAPI / Starlette** | ✅ Complete | ASGI | Excellent |
| **Sanic** | ✅ Complete | ASGI | Excellent |
| **aiohttp** | ✅ Complete | ASGI | Excellent |

---

## 🚀 Quick Start by Framework

### FastAPI

```python
from fastapi import FastAPI
from aioresilience import LoadShedder, CircuitBreaker, RateLimiter, Bulkhead
from aioresilience.integrations.fastapi import (
    LoadSheddingMiddleware,
    CircuitBreakerMiddleware,
    ResilienceMiddleware,  # Composite
)

app = FastAPI()

# Individual middleware
app.add_middleware(LoadSheddingMiddleware, load_shedder=LoadShedder(max_requests=1000))
app.add_middleware(CircuitBreakerMiddleware, circuit_breaker=CircuitBreaker(name="api"))

# Or use composite middleware
app.add_middleware(
    ResilienceMiddleware,
    rate_limiter=RateLimiter(name="api"),
    rate="1000/minute",
    load_shedder=LoadShedder(max_requests=500),
    bulkhead=Bulkhead(max_concurrent=100),
    circuit_breaker=CircuitBreaker(name="backend"),
    timeout=30.0
)

@app.get("/api/data")
async def get_data():
    return {"data": "..."}
```

**Features:**
- ✅ Modular middleware (separate files per pattern)
- ✅ Composite middleware (combine multiple patterns)
- ✅ Route-level decorators
- ✅ Dependency injection support
- ✅ Full async support

**See:** `aioresilience/integrations/fastapi/README.md`

---

### Sanic

```python
from sanic import Sanic, json
from aioresilience import CircuitBreaker, RateLimiter, LoadShedder
from aioresilience.integrations.sanic import (
    setup_resilience,
    circuit_breaker_route,
    rate_limit_route,
)

app = Sanic("MyApp")

# Global setup (applies to all routes)
setup_resilience(
    app,
    circuit_breaker=CircuitBreaker(name="api"),
    rate_limiter=RateLimiter(name="api"),
    rate="1000/minute",
    load_shedder=LoadShedder(max_requests=500),
    timeout=30.0
)

# Or use route decorators
@app.get("/api/data")
@circuit_breaker_route(CircuitBreaker(name="api"))
@rate_limit_route(RateLimiter(name="api"), "100/minute")
async def get_data(request):
    return json({"data": "..."})
```

**Features:**
- ✅ Full async support (no asyncio.run overhead)
- ✅ Route decorators
- ✅ Middleware setup
- ✅ Maximum performance (async all the way)

**See:** `aioresilience/integrations/sanic/README.md`

---

### aiohttp

```python
from aiohttp import web
from aioresilience import CircuitBreaker, RateLimiter, LoadShedder
from aioresilience.integrations.aiohttp import (
    create_resilience_middleware,
    circuit_breaker_handler,
    rate_limit_handler,
)

app = web.Application()

# Middleware (applies to all handlers)
app.middlewares.append(create_resilience_middleware(
    circuit_breaker=CircuitBreaker(name="api"),
    rate_limiter=RateLimiter(name="api"),
    rate="1000/minute",
    load_shedder=LoadShedder(max_requests=500),
    timeout=30.0
))

# Or use handler decorators
@circuit_breaker_handler(CircuitBreaker(name="api"))
@rate_limit_handler(RateLimiter(name="api"), "100/minute")
async def get_data(request):
    return web.json_response({"data": "..."})

app.router.add_get("/api/data", get_data)
web.run_app(app)
```

**Features:**
- ✅ Full async support
- ✅ Handler decorators
- ✅ Middleware factory
- ✅ Clean aiohttp integration

**See:** `aioresilience/integrations/aiohttp/README.md`

---

## 📋 Feature Comparison

| Feature | FastAPI | Sanic | aiohttp |
|---------|---------|-------|---------|
| **Circuit Breaker** | ✅ | ✅ | ✅ |
| **Retry** | ✅* | ✅* | ✅* |
| **Timeout** | ✅ | ✅ | ✅ |
| **Bulkhead** | ✅ | ✅ | ✅ |
| **Fallback** | ✅ | ✅ | ✅ |
| **Rate Limiting** | ✅ | ✅ | ✅ |
| **Load Shedding** | ✅ | ✅ | ✅ |
| **Middleware** | ✅ | ✅ | ✅ |
| **Decorators** | ✅ | ✅ | ✅ |
| **Composite Patterns** | ✅ | ✅ | ✅ |

*Available via decorators or manual integration

---

## 🎯 Choosing the Right Pattern

### When to Use What

**Circuit Breaker**: Protect against cascading failures
```python
# Use when calling external services
@circuit_breaker_route(circuit)
async def call_external_api():
    ...
```

**Rate Limiting**: Control request rates per client/user
```python
# Use for API endpoints
@rate_limit_route(limiter, "100/minute")
async def api_endpoint():
    ...
```

**Bulkhead**: Isolate resources and limit concurrency
```python
# Use for resource-intensive operations
@bulkhead_route(bulkhead)
async def database_query():
    ...
```

**Timeout**: Enforce time bounds on operations
```python
# Use for operations that might hang
@timeout_route(5.0)
async def slow_operation():
    ...
```

**Fallback**: Provide graceful degradation
```python
# Use for non-critical data
@with_fallback_route({"data": [], "status": "degraded"})
async def get_recommendations():
    ...
```

---

## 🏗️ Architecture Patterns

### 1. Defense in Depth (Layered)

```python
# Apply multiple patterns to critical endpoints
@app.route("/critical")
@timeout_route(5.0)           # Outer: time bound
@circuit_breaker_route(cb)    # Next: fail fast
@bulkhead_route(bh)           # Next: resource isolation
@rate_limit_route(rl, "10/s") # Inner: rate control
async def critical_operation():
    ...
```

### 2. Global + Specific

```python
# Global protection for all routes
setup_resilience(app, timeout=30.0, load_shedder=shedder)

# Additional protection for specific routes
@app.route("/expensive")
@bulkhead_route(Bulkhead(max_concurrent=5))
async def expensive_operation():
    ...
```

### 3. Composite Middleware

```python
# Single middleware with multiple patterns
app.add_middleware(
    ResilienceMiddleware,
    rate_limiter=rate_limiter,
    rate="1000/minute",
    load_shedder=load_shedder,
    bulkhead=bulkhead,
    circuit_breaker=circuit,
    timeout=30.0
)
```

---

## 📚 Additional Resources

- **Main Documentation**: `README.md`
- **FastAPI Integration**: `aioresilience/integrations/fastapi/README.md`
- **Sanic Integration**: `aioresilience/integrations/sanic/README.md`
- **aiohttp Integration**: `aioresilience/integrations/aiohttp/README.md`

---

**All integrations maintain backward compatibility and follow semantic versioning.**
