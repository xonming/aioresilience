# aioresilience - Fault Tolerance Library for Asyncio

[![PyPI version](https://badge.fury.io/py/aioresilience.svg)](https://badge.fury.io/py/aioresilience)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/aioresilience)](https://pypi.org/project/aioresilience/)
[![CI/CD](https://github.com/xonming/aioresilience/actions/workflows/ci.yml/badge.svg)](https://github.com/xonming/aioresilience/actions/workflows/ci.yml)
[![MIT License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Table of Contents

- [Introduction](#introduction)
- [Features](#features)
- [Installation](#installation)
- [Overview](#overview)
- [Resilience Patterns](#resilience-patterns)
- [Logging Configuration](#logging-configuration)
- [Usage Examples](#usage-examples)
- [Framework Integrations](#framework-integrations)
- [Event System](#event-system)
- [Architecture](#architecture)
- [Performance](#performance)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

## Introduction

aioresilience is a comprehensive fault tolerance library for Python's asyncio ecosystem, providing 9 resilience patterns with a powerful event system for monitoring.

**Core Capabilities:**
- **9 Resilience Patterns**: Circuit Breaker, Retry, Timeout, Bulkhead, Fallback, Rate Limiter, Load Shedder, Backpressure, and Adaptive Concurrency
- **Event-Driven Observability**: Local and global event handlers for comprehensive monitoring
- **Decorator & Context Manager APIs**: Flexible integration styles - use decorators, context managers, or direct calls
- **Composable**: Stack multiple patterns on any async function
- **Framework Integrations**: First-class support for FastAPI, Sanic, and aiohttp

aioresilience requires Python 3.9+.

```python
from aioresilience import CircuitBreaker, RateLimiter, LoadShedder, circuit_breaker, with_load_shedding

# Create a CircuitBreaker with default configuration
circuit = CircuitBreaker(name="backendService", failure_threshold=5)

# Create a RateLimiter with local in-memory storage
rate_limiter = RateLimiter(name="backendService")

# Create a LoadShedder with default configuration
load_shedder = LoadShedder(max_requests=1000)

# Example: Your backend service call
async def call_external_api():
    # Simulated API call
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()

# Decorate your function with Circuit Breaker and Load Shedding
@circuit_breaker("backendService", failure_threshold=5)
@with_load_shedding(load_shedder, priority="normal")
async def decorated_call(user_id: str):
    # Check rate limit
    if await rate_limiter.check_rate_limit(user_id, "100/minute"):
        return await call_external_api()
    else:
        raise Exception("Rate limit exceeded")

# Execute the decorated function and handle exceptions
try:
    result = await decorated_call("user_123")
except Exception as e:
    result = "Fallback value"

# Or call directly through the circuit breaker
result = await circuit.call(call_external_api)
```

> **Note:** With aioresilience you don't have to go all-in, you can [**pick what you need**](https://pypi.org/project/aioresilience/).

## Features

- **9 Resilience Patterns** - Circuit Breaker, Retry, Timeout, Bulkhead, Fallback, Rate Limiter, Load Shedder, Backpressure, Adaptive Concurrency
- **Event System** - Comprehensive observability with local and global event handlers
- **Flexible Logging** - Silent by default, supports any logging framework (loguru, structlog, etc.)
- **Async-First** - Built for asyncio from the ground up
- **Decorator & Context Manager** - Flexible API styles
- **Type Hints** - Full PEP 484 type annotations
- **Composable** - Stack multiple patterns on any function
- **Framework Integrations** - FastAPI, Sanic, aiohttp middleware
- **Optional Dependencies** - Use only what you need

## Documentation

Complete documentation is available in this README and through Python docstrings.

## Installation

```bash
pip install aioresilience
```

<details>
<summary><b>📦 Optional Features (click to expand)</b></summary>

```bash
# Redis-based distributed rate limiting
pip install aioresilience[redis]

# System metrics monitoring (CPU/memory)
pip install aioresilience[system]

# Framework integrations
pip install aioresilience[fastapi]      # FastAPI/Starlette
pip install aioresilience[sanic]        # Sanic
pip install aioresilience[aiohttp]      # aiohttp
pip install aioresilience[integrations] # All frameworks

# Development dependencies
pip install aioresilience[dev]

# Everything
pip install aioresilience[all]
```

</details>

## Overview

aioresilience provides the following resilience patterns:

* **Circuit Breaker** - Circuit breaking with state management
* **Rate Limiter** - Rate limiting (local and distributed)
* **Load Shedder** - Load shedding (basic and system-aware)
* **Backpressure Manager** - Backpressure management with water marks
* **Adaptive Concurrency Limiter** - Adaptive concurrency limiting with AIMD algorithm
* **Retry Policy** - Retry with exponential/linear/constant backoff
* **Timeout Manager** - Timeout and deadline management
* **Bulkhead** - Resource isolation and concurrency limiting
* **Fallback Handler** - Graceful degradation with fallback values
* **Event System** - Local and global event handlers for observability

### Framework Integrations

Seamless integration with popular async Python web frameworks:

* **FastAPI / Starlette** - Middleware and dependency injection
* **Sanic** - Async-native middleware and decorators
* **aiohttp** - Handler decorators and middleware

See [INTEGRATIONS.md](INTEGRATIONS.md) for detailed integration guides.

> **Note:** All core modules are included in the base package. Use optional dependencies to enable additional features.

> **Tip:** For all features install with `pip install aioresilience[all]`.

## Resilience Patterns

| Name | How Does It Work? | Description |
|------|-------------------|-------------|
| **Circuit Breaker** | Temporarily blocks possible failures | When a system is seriously struggling, failing fast is better than making clients wait. Prevents cascading failures by monitoring error rates and opening the circuit when thresholds are exceeded. |
| **Retry** | Automatic retry with backoff | Automatically retry failed operations with configurable strategies (exponential, linear, constant) and jitter to prevent thundering herd. |
| **Timeout** | Time-bound operations | Set maximum execution time for operations. Supports both relative timeouts and absolute deadlines. |
| **Bulkhead** | Isolate resources | Limit concurrent access to resources to prevent resource exhaustion. Isolates failures to specific resource pools. |
| **Fallback** | Graceful degradation | Provide alternative responses when primary operation fails. Supports static values, callables, and chained fallback strategies. |
| **Rate Limiter** | Limits executions per time period | Control the rate of incoming requests with configurable windows (second, minute, hour, day). Supports both local (in-memory) and distributed (Redis) backends. |
| **Load Shedder** | Rejects requests under high load | Protect your system by rejecting new requests when load exceeds thresholds. Supports request-count-based and system-metric-based (CPU/memory) shedding. |
| **Backpressure Manager** | Controls flow in async pipelines | Signal upstream components to slow down when downstream is overloaded. Uses water marks (high/low) for graceful flow control. |
| **Adaptive Concurrency** | Auto-adjusts concurrency limits | Dynamically adjust concurrency based on success rate using AIMD algorithm. Similar to TCP congestion control - additive increase, multiplicative decrease. |

*Above table is inspired by [Polly: resilience policies](https://github.com/App-vNext/Polly#resilience-policies) and [resilience4j](https://github.com/resilience4j/resilience4j).*

## Logging Configuration

<details>
<summary><b>🔧 Logging Setup (click to expand)</b></summary>

aioresilience follows Python library best practices with **silent logging by default** (NullHandler). This gives you complete control over how errors and operational logs are handled.

### Default Behavior (Silent)

By default, aioresilience emits no logs:

```python
from aioresilience import CircuitBreaker

# No logs are emitted - library is silent by default
circuit = CircuitBreaker("api")
```

### Enable Standard Python Logging

Configure standard Python logging for aioresilience:

```python
import logging
from aioresilience import configure_logging

# Enable logging with DEBUG level
configure_logging(logging.DEBUG)

# Now you'll see logs from aioresilience
circuit = CircuitBreaker("api")
```

### Custom Logging Framework Integration

Use **any** logging framework (loguru, structlog, etc.) with the error handler:

#### With Loguru

```python
from loguru import logger
from aioresilience import set_error_handler

# Route aioresilience errors to loguru
set_error_handler(
    lambda name, exc, ctx: logger.error(
        f"[{name}] {exc.__class__.__name__}: {exc}",
        **ctx
    )
)
```

#### With Structlog

```python
import structlog
from aioresilience import set_error_handler

log = structlog.get_logger()

set_error_handler(
    lambda name, exc, ctx: log.error(
        "aioresilience_error",
        module=name,
        exception_type=exc.__class__.__name__,
        exception=str(exc),
        **ctx
    )
)
```

### Custom Format

```python
from aioresilience import configure_logging
import logging

configure_logging(
    level=logging.INFO,
    format_string='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
)
```

### Disable Logging

```python
from aioresilience import disable_logging

# Explicitly disable all logging (already default)
disable_logging()
```

### Check Logging Status

```python
from aioresilience import is_logging_enabled

if is_logging_enabled():
    print("Logging is configured")
else:
    print("Logging is silent")
```

### Logging API Reference

| Function | Description |
|----------|-------------|
| `configure_logging(level, handler, format_string)` | Enable standard Python logging |
| `set_error_handler(handler)` | Set custom error handler for any framework |
| `disable_logging()` | Reset to silent state (NullHandler) |
| `is_logging_enabled()` | Check if logging is configured |

</details>

## Usage Examples

### Circuit Breaker

The following example shows how to decorate an async function with a Circuit Breaker and how to handle state transitions.

```python
import asyncio
import httpx
from aioresilience import CircuitBreaker, circuit_breaker

# Simulates a Backend Service
class BackendService:
    async def do_something(self):
        # Simulate API call
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.example.com/data")
            return response.json()

backend_service = BackendService()

# Create a CircuitBreaker with custom configuration
circuit = CircuitBreaker(
    name="backendName",
    failure_threshold=5,      # Open after 5 consecutive failures
    recovery_timeout=60.0,    # Wait 60 seconds before trying half-open
    success_threshold=2       # Need 2 successes to close from half-open
)

# Decorate your call to BackendService.do_something()
async def call_backend():
    if await circuit.can_execute():
        try:
            result = await circuit.call(backend_service.do_something)
            return result
        except Exception as e:
            # Circuit breaker automatically tracks the failure
            raise
    else:
        raise Exception("Circuit breaker is OPEN")

# Or use the decorator pattern
@circuit_breaker("backendName", failure_threshold=5)
async def decorated_backend_call():
    return await backend_service.do_something()

# Execute with fallback
async def call_with_fallback():
    try:
        result = await decorated_backend_call()
        return result
    except Exception:
        return {"data": "fallback_value"}

# When you don't want to decorate your function
result = await circuit.call(backend_service.do_something)
```

#### Circuit Breaker States

The circuit breaker has three states:

* **CLOSED**: Normal operation, requests pass through
* **OPEN**: Failure threshold exceeded, requests fail fast
* **HALF_OPEN**: Testing recovery, limited requests allowed

<details>
<summary><b>Monitoring Circuit Breaker</b></summary>

**Recommended: Event-Driven Monitoring**

For real-time monitoring and alerting, use event handlers:

```python
from aioresilience import CircuitBreaker

circuit = CircuitBreaker(name="backend")

# React to state changes in real-time
@circuit.events.on("state_change")
async def on_state_change(event):
    print(f"Circuit {event.pattern_name}: {event.old_state} → {event.new_state}")
    # Send alert, update dashboard, etc.

@circuit.events.on("circuit_opened")
async def on_circuit_opened(event):
    # Alert your team when circuit opens
    await send_alert(f"Circuit {event.pattern_name} opened!")
```

**Alternative: Polling Metrics**

For periodic health checks or dashboards, you can poll metrics:

```python
# Get current state (synchronous)
state = circuit.get_state()
print(f"Circuit state: {state}")

# Get detailed metrics for dashboards
metrics = circuit.get_metrics()
print(f"Total requests: {metrics['total_requests']}")
print(f"Failed requests: {metrics['failed_requests']}")
print(f"Failure rate: {metrics['failure_rate']:.2%}")

# Access global circuit breaker manager
from aioresilience import get_circuit_breaker, get_all_circuit_metrics

# Get or create a circuit breaker
backend_circuit = get_circuit_breaker("backend", failure_threshold=3)

# Get metrics for all circuit breakers (useful for health endpoints)
all_metrics = get_all_circuit_metrics()
for name, metrics in all_metrics.items():
    print(f"{name}: {metrics['state']}")
```

**When to Use Each:**
- **Events**: Real-time alerts, immediate reactions, logging
- **Polling**: Health check endpoints, periodic dashboard updates, batch monitoring

</details>

### Rate Limiter

The following example shows how to restrict the calling rate to not be higher than 10 requests per second.

```python
import asyncio
from aioresilience import RateLimiter

# Create a RateLimiter (local/in-memory)
rate_limiter = RateLimiter(name="backendName")

# Check rate limit for a specific key (e.g., user ID)
async def handle_request(user_id: str):
    if await rate_limiter.check_rate_limit(user_id, "10/second"):
        # Request is within rate limit
        return {"status": "success", "data": "..."}
    else:
        # Rate limit exceeded
        raise Exception("Rate limit exceeded")

# Example: Testing rate limits
async def test_rate_limit():
    # First call succeeds
    try:
        result = await handle_request("user_123")
        print("Request successful")
    except Exception as e:
        print(f"Request failed: {e}")
    
    # If you make 11 calls in one second, the 11th will fail
    for i in range(11):
        try:
            result = await handle_request("user_123")
            print(f"Call {i+1} successful")
        except Exception as e:
            print(f"Call {i+1} failed: {e}")

# Run the test
asyncio.run(test_rate_limit())
```

#### Rate Limit Formats

aioresilience supports multiple time periods:

* `"10/second"` - 10 requests per second
* `"100/minute"` - 100 requests per minute
* `"1000/hour"` - 1000 requests per hour
* `"10000/day"` - 10000 requests per day

#### Distributed Rate Limiting with Redis

For multi-instance applications, use Redis-based distributed rate limiting:

```python
from aioresilience.rate_limiting import RedisRateLimiter

# Create a Redis-backed rate limiter
rate_limiter = RedisRateLimiter(name="backendName")
await rate_limiter.init_redis("redis://localhost:6379")

# Use the same API - now shared across all instances
if await rate_limiter.check_rate_limit("user_123", "1000/hour"):
    result = await backend_service.do_something()
else:
    raise Exception("Rate limit exceeded")

# Don't forget to close the connection when done
await rate_limiter.close()
```

> **Note:** Redis rate limiter uses a sliding window algorithm with sorted sets for accurate distributed rate limiting.

### Load Shedding

There are two load shedding implementations.

#### BasicLoadShedder

The following example shows how to shed load based on request count:

```python
from aioresilience import LoadShedder

# Create a LoadShedder with request count limits
load_shedder = LoadShedder(
    max_requests=1000,       # Maximum concurrent requests
    max_queue_depth=500      # Maximum queue depth
)

# Use in your request handler
async def handle_request():
    if await load_shedder.acquire():
        try:
            # Process the request
            result = await backend_service.do_something()
            return result
        finally:
            await load_shedder.release()
    else:
        # Load shedding - reject request
        raise Exception("Service overloaded")

# Or use the decorator
from aioresilience import with_load_shedding

@with_load_shedding(load_shedder, priority="normal")
async def process_request():
    return await backend_service.do_something()
```

#### SystemLoadShedder

The following example shows how to shed load based on system metrics (CPU and memory):

```python
from aioresilience.load_shedding import SystemLoadShedder

# Create a system-aware load shedder
load_shedder = SystemLoadShedder(
    max_requests=1000,
    cpu_threshold=85.0,      # Shed load if CPU > 85%
    memory_threshold=85.0    # Shed load if memory > 85%
)

# Use the same API as BasicLoadShedder
async def handle_request():
    if await load_shedder.acquire(priority="normal"):
        try:
            result = await backend_service.do_something()
            return result
        finally:
            await load_shedder.release()
    else:
        raise Exception("Service overloaded - high system load")

# High priority requests can bypass some checks
if await load_shedder.acquire(priority="high"):
    # High priority request processing
    pass
```

> **Note:** SystemLoadShedder requires the `psutil` package. Install with `pip install aioresilience[system]`.

### Backpressure Management

Control flow in async processing pipelines using water marks:

```python
from aioresilience import BackpressureManager

# Create a backpressure manager
backpressure = BackpressureManager(
    max_pending=1000,        # Hard limit on pending items
    high_water_mark=800,     # Start applying backpressure
    low_water_mark=200       # Stop applying backpressure
)

# Use in async pipeline
async def process_stream(items):
    for item in items:
        # Try to acquire slot (with timeout)
        if await backpressure.acquire(timeout=5.0):
            try:
                await process_item(item)
            finally:
                await backpressure.release()
        else:
            # Backpressure timeout - item rejected
            logger.warning(f"Item rejected due to backpressure")

# Or use the decorator
from aioresilience import with_backpressure

@with_backpressure(backpressure, timeout=5.0)
async def process_item(item):
    # Your processing logic
    await asyncio.sleep(0.1)
    return item
```

### Adaptive Concurrency Limiting

Automatically adjust concurrency limits based on success rate:

```python
from aioresilience import AdaptiveConcurrencyLimiter

# Create an adaptive limiter with AIMD algorithm
limiter = AdaptiveConcurrencyLimiter(
    initial_limit=100,       # Starting concurrency
    min_limit=10,            # Minimum concurrency
    max_limit=1000,          # Maximum concurrency
    increase_rate=1.0,       # Additive increase
    decrease_factor=0.9      # Multiplicative decrease
)

# Use in your request handler
async def handle_request():
    if await limiter.acquire():
        try:
            result = await backend_service.do_something()
            # Report success
            await limiter.release(success=True)
            return result
        except Exception as e:
            # Report failure
            await limiter.release(success=False)
            raise
    else:
        raise Exception("Concurrency limit reached")

# Check current statistics
stats = limiter.get_stats()
print(f"Current limit: {stats['current_limit']}")
print(f"Active requests: {stats['active_count']}")
```

> **Note:** The AIMD algorithm increases the limit linearly on success and decreases it exponentially on failure, similar to TCP congestion control.

### Retry Pattern

Automatically retry failed operations with exponential backoff and jitter:

```python
from aioresilience import RetryPolicy, retry, RetryStrategy

# Using RetryPolicy class
policy = RetryPolicy(
    max_attempts=5,
    initial_delay=1.0,
    max_delay=60.0,
    backoff_multiplier=2.0,
    strategy=RetryStrategy.EXPONENTIAL,
    jitter=0.1,
)

async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()

# Execute with retry
result = await policy.execute(fetch_data)

# Or use the decorator
@retry(
    max_attempts=3,
    initial_delay=0.5,
    strategy=RetryStrategy.EXPONENTIAL
)
async def fetch_user(user_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/users/{user_id}")
        response.raise_for_status()
        return response.json()

# Will automatically retry on exceptions
user = await fetch_user("123")
```

#### Retry Strategies

Three backoff strategies are available:

* **Exponential**: Delays increase exponentially (1s, 2s, 4s, 8s...)
* **Linear**: Delays increase linearly (1s, 2s, 3s, 4s...)
* **Constant**: Same delay every time (1s, 1s, 1s, 1s...)

#### Predefined Policies

```python
from aioresilience import RetryPolicies

# Default: 3 attempts, exponential backoff
policy = RetryPolicies.default()

# Aggressive: 5 attempts, fast exponential backoff
policy = RetryPolicies.aggressive()

# Conservative: 3 attempts, linear backoff with high jitter
policy = RetryPolicies.conservative()

# Network-oriented: handles connection errors
policy = RetryPolicies.network()
```

### Timeout Pattern

Set maximum execution time for async operations:

```python
from aioresilience import TimeoutManager, timeout, with_timeout

# Using TimeoutManager class
manager = TimeoutManager(timeout=5.0)

async def slow_operation():
    await asyncio.sleep(10.0)
    return "result"

# Will raise OperationTimeoutError after 5 seconds
try:
    result = await manager.execute(slow_operation)
except OperationTimeoutError:
    print("Operation timed out")

# Or use the decorator
@timeout(3.0)
async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()

# Convenience function for one-off timeouts
result = await with_timeout(fetch_data, 5.0)
```

#### Deadline Management

For absolute time constraints:

```python
from aioresilience import DeadlineManager, with_deadline
import time

# Set an absolute deadline
deadline = time.time() + 10.0  # 10 seconds from now
manager = DeadlineManager(deadline=deadline)

async def process_request():
    # Multiple operations sharing the same deadline
    data1 = await manager.execute(fetch_data)
    data2 = await manager.execute(process_data, data1)
    return data2

# Or use convenience function
result = await with_deadline(fetch_data, deadline)
```

### Bulkhead Pattern

Isolate resources and limit concurrent access:

```python
from aioresilience import Bulkhead, bulkhead

# Create a bulkhead for database connections
db_bulkhead = Bulkhead(
    max_concurrent=10,    # Max 10 concurrent database operations
    max_waiting=20,       # Max 20 requests waiting in queue
    timeout=5.0,          # Max 5 seconds wait time
    name="database"
)

async def query_database(query: str):
    async with db_bulkhead:
        # Only 10 of these can run concurrently
        # Your database query here
        result = {"query": query, "status": "success"}
        return result

# Or use as a function executor with a callable
async def execute_query(query: str):
    # Your database logic here
    return {"query": query, "status": "success"}

result = await db_bulkhead.execute(execute_query, "SELECT * FROM users")

# Or use the decorator
@bulkhead(max_concurrent=5, max_waiting=10)
async def call_external_api(endpoint: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/{endpoint}")
        return response.json()

# Get metrics
metrics = db_bulkhead.get_metrics()
print(f"Current active: {metrics['current_active']}")
print(f"Peak active: {metrics['peak_active']}")
print(f"Rejected: {metrics['rejected_requests']}")
```

#### Bulkhead Registry

Manage multiple resource pools:

```python
from aioresilience import get_bulkhead

# Define your operations
async def call_api():
    # Your API call logic
    return {"status": "success"}

async def query_db():
    # Your database query logic
    return {"rows": []}

async def get_cache():
    # Your cache operation logic
    return {"cached": True}

# Get or create named bulkheads
api_bulkhead = await get_bulkhead("external_api", max_concurrent=10)
db_bulkhead = await get_bulkhead("database", max_concurrent=20)
cache_bulkhead = await get_bulkhead("cache", max_concurrent=50)

# Use them independently
await api_bulkhead.execute(call_api)
await db_bulkhead.execute(query_db)
await cache_bulkhead.execute(get_cache)
```

### Fallback Pattern

Provide alternative responses when operations fail:

```python
import httpx
from aioresilience import fallback, chained_fallback, with_fallback

# Simple static fallback
@fallback([])
async def fetch_items():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/items")
        return response.json()

# If fetch_items fails, returns empty list []

# Fallback with callable
@fallback(lambda: {"status": "unavailable"})
async def get_service_status():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/status")
        return response.json()

# Async fallback function
async def get_cached_data(*args, **kwargs):
    # Simulated cache lookup
    return {"cached": True, "data": "cached_user_data"}

@fallback(get_cached_data)
async def fetch_user_data(user_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/users/{user_id}")
        return response.json()

# If API fails, tries cache; if cache fails, raises exception
```

#### Chained Fallbacks

Multiple fallback strategies in sequence:

```python
import httpx
from aioresilience import chained_fallback

async def get_from_cache(user_id):
    # Simulated cache lookup
    return {"cached": True, "user_id": user_id}

async def get_from_backup_api(user_id):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://backup-api.example.com/users/{user_id}")
        return response.json()

DEFAULT_USER = {"id": None, "name": "Guest", "email": None}

@chained_fallback(
    get_from_cache,           # Try cache first
    get_from_backup_api,      # Then backup API
    DEFAULT_USER              # Finally use default
)
async def get_user(user_id: str):
    # Try primary API
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.example.com/users/{user_id}")
        response.raise_for_status()
        return response.json()

# Tries: primary API → cache → backup API → default value
user = await get_user("123")
```

#### Combining Patterns

Retry with fallback for robust error handling:

```python
@retry(max_attempts=3, initial_delay=1.0)
@fallback({"data": [], "status": "degraded"})
async def fetch_critical_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/critical-data")
        response.raise_for_status()
        return response.json()

# Will retry up to 3 times, then use fallback if all fail
```

## Framework Integrations

aioresilience provides **fully configurable** middleware and decorators for FastAPI, Sanic, and aiohttp with zero hardcoded values.

**Key Features:**
- All error messages configurable
- All HTTP status codes configurable
- All Retry-After headers configurable
- Custom response factories for complete control

See [INTEGRATIONS.md](INTEGRATIONS.md) for comprehensive guides.

### FastAPI Integration

FastAPI provides modular middleware and decorators with full configurability:

```python
from fastapi import FastAPI
from aioresilience import CircuitBreaker, LoadShedder, RetryPolicy
from aioresilience.integrations.fastapi import (
    CircuitBreakerMiddleware,
    LoadSheddingMiddleware,
    TimeoutMiddleware,
    BulkheadMiddleware,
    FallbackMiddleware,
    ResilienceMiddleware,    # Composite - combines multiple patterns
    retry_route,             # Route decorator (recommended for retry logic)
)

app = FastAPI()

# Circuit Breaker - Fully customizable
app.add_middleware(
    CircuitBreakerMiddleware,
    circuit_breaker=CircuitBreaker("api", failure_threshold=5),
    error_message="Service temporarily down",  # Custom message
    status_code=503,                           # Custom status
    retry_after=30,                            # Custom retry delay
    include_circuit_info=False,                # Hide internal details
    exclude_paths={"/health", "/metrics"},     # O(1) set lookup
)

# Load Shedding - Configurable
app.add_middleware(
    LoadSheddingMiddleware,
    load_shedder=LoadShedder(max_requests=1000),
    error_message="Too busy - please retry",
    retry_after=10,
    priority_header="X-Request-Priority",      # Custom header name
    default_priority="normal",
)

# Timeout - Configurable
app.add_middleware(
    TimeoutMiddleware,
    timeout=30.0,
    error_message="Request took too long",
    status_code=408,
)

# Fallback
app.add_middleware(
    FallbackMiddleware,
    fallback_response={"status": "degraded", "data": []},
    log_errors=True,
)

# Retry - Use route-level decorator (recommended over middleware)
@app.get("/api/data")
@retry_route(RetryPolicy(max_attempts=3, initial_delay=1.0))
async def get_data():
    # Automatic retry on failure with exponential backoff
    return {"data": "..."}
```

### Rate Limiting Dependency

```python
from fastapi import FastAPI, Depends
from aioresilience import RateLimiter
from aioresilience.integrations.fastapi import rate_limit_dependency

app = FastAPI()
rate_limiter = RateLimiter(name="api")

# Basic usage
@app.get("/api/data", dependencies=[
    Depends(rate_limit_dependency(rate_limiter, "100/minute"))
])
async def get_data():
    return {"data": "..."}

# Fully customized
@app.get("/api/premium", dependencies=[
    Depends(rate_limit_dependency(
        rate_limiter,
        "1000/minute",
        error_message="Premium tier limit exceeded",
        status_code=429,
        retry_after=30,
        key_func=lambda req: req.headers.get("X-User-ID"),  # Custom key
    ))
])
async def premium_data():
    return {"data": "premium"}
```

### Custom Client IP Extraction

```python
from fastapi import Request
from aioresilience.integrations.fastapi import get_client_ip

@app.middleware("http")
async def custom_middleware(request: Request, call_next):
    client_ip = get_client_ip(request)
    # Supports X-Forwarded-For and X-Real-IP headers
    logger.info(f"Request from {client_ip}")
    response = await call_next(request)
    return response
```

### Sanic Integration

Sanic is async-native with **fully configurable** middleware and decorators.

```python
from sanic import Sanic, json
from aioresilience import CircuitBreaker, RateLimiter, LoadShedder
from aioresilience.integrations.sanic import (
    setup_resilience,
    circuit_breaker_route,
    rate_limit_route,
    timeout_route,
    bulkhead_route,
)

app = Sanic("MyApp")

# Global resilience setup - Fully configurable
setup_resilience(
    app,
    circuit_breaker=CircuitBreaker(name="api"),
    rate_limiter=RateLimiter(name="api"),
    rate="1000/minute",
    load_shedder=LoadShedder(max_requests=500),
    timeout=30.0,
    # All customizable
    exclude_paths={"/health", "/metrics", "/admin"},
    circuit_error_message="API temporarily unavailable",
    circuit_status_code=503,
    circuit_retry_after=60,
    rate_error_message="Too many requests",
    rate_retry_after=120,
    load_error_message="Server overloaded",
    priority_header="X-Priority",
)

# Or use route decorators - Also configurable
@app.get("/api/data")
@circuit_breaker_route(
    CircuitBreaker(name="api"),
    error_message="Service down",
    status_code=503,
    retry_after=30,
    include_info=False,  # Hide circuit details
)
async def get_data(request):
    return json({"data": "..."})

@app.get("/api/limited")
@rate_limit_route(
    RateLimiter(name="api"),
    "100/minute",
    error_message="Rate limit hit",
    retry_after=60,
)
async def limited_endpoint(request):
    return json({"data": "limited"})
```

### aiohttp Integration

Clean middleware and decorators with **full configurability** for aiohttp.

```python
from aiohttp import web
from aioresilience import CircuitBreaker, RateLimiter, LoadShedder
from aioresilience.integrations.aiohttp import (
    create_resilience_middleware,
    circuit_breaker_handler,
    rate_limit_handler,
    timeout_handler,
)

app = web.Application()

# Add resilience middleware - Fully configurable
app.middlewares.append(create_resilience_middleware(
    circuit_breaker=CircuitBreaker(name="api"),
    rate_limiter=RateLimiter(name="api"),
    rate="1000/minute",
    load_shedder=LoadShedder(max_requests=500),
    timeout=30.0,
    # All customizable
    exclude_paths={"/health", "/metrics"},
    circuit_error_message="API down",
    circuit_status_code=503,
    circuit_retry_after=45,
    rate_error_message="Limit reached",
    rate_retry_after=90,
    load_error_message="Too busy",
    priority_header="X-Priority",
))

# Or use handler decorators - Also configurable
@circuit_breaker_handler(
    CircuitBreaker(name="api"),
    error_message="Service unavailable",
    status_code=503,
    retry_after=30,
    include_info=False,
)
async def get_data(request):
    return web.json_response({"data": "..."})

@rate_limit_handler(
    RateLimiter(name="api"),
    "100/minute",
    error_message="Rate limit exceeded",
    retry_after=60,
)
async def limited_data(request):
    return web.json_response({"data": "limited"})

app.router.add_get("/api/data", get_data)
app.router.add_get("/api/limited", limited_data)
```

For more details, see [INTEGRATIONS.md](INTEGRATIONS.md).

## Event System

All resilience patterns emit events for logging, monitoring, and metrics. The event system supports both local event handlers (per pattern instance) and a global event bus for centralized monitoring.

### Local Event Handlers

Each pattern has its own `EventEmitter` accessible via the `.events` attribute:

```python
from aioresilience import CircuitBreaker
import logging

logger = logging.getLogger(__name__)

circuit = CircuitBreaker(name="backend", failure_threshold=5)

# Register event handlers using decorator syntax
@circuit.events.on("state_change")
async def on_state_change(event):
    logger.warning(f"Circuit {event.name} changed state: "
                   f"{event.metadata['from_state']} → {event.metadata['to_state']}")

@circuit.events.on("call_success")
async def on_success(event):
    logger.debug(f"Circuit {event.name}: successful call")

@circuit.events.on("call_failure")
async def on_failure(event):
    logger.error(f"Circuit {event.name}: call failed - {event.metadata.get('error')}")

# Or register handlers directly
async def on_circuit_opened(event):
    logger.critical(f"⚠️  Circuit {event.name} OPENED! System degraded.")

circuit.events.on("circuit_opened", on_circuit_opened)

# Wildcard handler to capture all events
@circuit.events.on("*")
async def log_all_events(event):
    logger.info(f"Event: {event.event_type} from {event.name}")
```

### Global Event Bus

Monitor events across all patterns using the global event bus:

```python
from aioresilience import CircuitBreaker, RateLimiter, Bulkhead
from aioresilience.events import event_bus
import logging

logger = logging.getLogger(__name__)

# Register global event handlers
@event_bus.on("state_change")
async def monitor_all_state_changes(event):
    logger.warning(f"[{event.pattern_type}] {event.name}: "
                   f"{event.metadata['from_state']} → {event.metadata['to_state']}")

@event_bus.on("rate_limit_exceeded")
async def alert_on_rate_limit(event):
    logger.warning(f"Rate limit exceeded for key: {event.metadata.get('key')}")

@event_bus.on("*")
async def collect_metrics(event):
    # Send to monitoring system (Prometheus, DataDog, etc.)
    metrics_collector.record(
        event_type=event.event_type,
        pattern=event.pattern_type,
        timestamp=event.timestamp
    )

# All patterns emit to both local handlers AND the global bus
circuit = CircuitBreaker(name="api")
rate_limiter = RateLimiter(name="api")
bulkhead = Bulkhead(max_concurrent=100)
```

### Event Types by Pattern

**Circuit Breaker:**
- `state_change` - State transitions (CLOSED ↔ OPEN ↔ HALF_OPEN)
- `circuit_opened` - Circuit opened due to failures
- `circuit_closed` - Circuit recovered
- `call_success` - Successful call
- `call_failure` - Failed call

**Rate Limiter:**
- `rate_limit_exceeded` - Request rejected
- `rate_limit_passed` - Request allowed

**Bulkhead:**
- `bulkhead_rejected` - Request rejected (full)
- `bulkhead_accepted` - Request accepted

**Load Shedder:**
- `request_shed` - Request shed due to overload
- `request_accepted` - Request accepted

**Timeout:**
- `timeout_exceeded` - Operation timed out
- `timeout_success` - Completed within timeout

**Fallback:**
- `fallback_triggered` - Fallback value returned

**Retry:**
- `retry_attempt` - Retry attempt started
- `retry_success` - Retry succeeded
- `retry_exhausted` - All retries failed

### Getting Metrics

You can still poll metrics synchronously when needed:

```python
# Circuit Breaker metrics
metrics = circuit.get_metrics()
print(f"State: {metrics['state']}, Failures: {metrics['consecutive_failures']}")

# Load Shedder statistics
stats = load_shedder.get_stats()
print(f"Active: {stats['active_requests']}, Shed: {stats['total_shed']}")

# Rate Limiter statistics
stats = rate_limiter.get_stats()
print(f"Active limiters: {stats['active_limiters']}")
```

For detailed examples, see `examples/events_example.py`.

## Architecture

<details>
<summary><b>📁 Project Structure (click to expand)</b></summary>

aioresilience follows a modular architecture with minimal required dependencies:

```
aioresilience/
├── __init__.py                  # Main exports
├── logging.py                   # Logging configuration utilities (no dependencies)
├── events/                      # Event system (no dependencies)
│   ├── __init__.py
│   ├── emitter.py              # Local event handlers per pattern
│   ├── bus.py                  # Global event bus
│   └── types.py                # Event types and dataclasses
├── circuit_breaker.py           # Circuit breaker pattern (no dependencies)
├── retry.py                     # Retry with backoff strategies (no dependencies)
├── timeout.py                   # Timeout and deadline management (no dependencies)
├── bulkhead.py                  # Resource isolation (no dependencies)
├── fallback.py                  # Graceful degradation (no dependencies)
├── backpressure.py              # Backpressure management (no dependencies)
├── adaptive_concurrency.py      # Adaptive concurrency limiting (no dependencies)
├── rate_limiting/
│   ├── __init__.py
│   ├── local.py                 # In-memory rate limiting (requires: aiolimiter)
│   └── redis.py                 # Distributed rate limiting (requires: redis)
├── load_shedding/
│   ├── __init__.py
│   ├── basic.py                 # Basic load shedding (no dependencies)
│   └── system.py                # System-aware load shedding (requires: psutil)
└── integrations/
    ├── __init__.py
    ├── fastapi/                 # FastAPI integration (requires: fastapi)
    │   ├── __init__.py
    │   ├── circuit_breaker.py
    │   ├── load_shedding.py
    │   ├── timeout.py
    │   ├── bulkhead.py
    │   ├── retry.py
    │   ├── fallback.py
    │   ├── backpressure.py
    │   ├── adaptive_concurrency.py
    │   ├── composite.py         # Composite resilience middleware
    │   ├── decorators.py        # Route-level decorators (retry_route, etc.)
    │   ├── dependencies.py      # Dependency injection utilities
    │   ├── utils.py
    │   └── README.md
    ├── sanic/                   # Sanic integration (requires: sanic)
    │   ├── __init__.py
    │   ├── decorators.py
    │   ├── middleware.py
    │   └── utils.py
    └── aiohttp/                 # aiohttp integration (requires: aiohttp)
        ├── __init__.py
        ├── decorators.py
        ├── middleware.py
        └── utils.py
```

### Core Dependencies

- **Required**: `aiolimiter>=1.0.0` (for rate limiting)
- **Optional**: 
  - `redis>=4.5.0` (for distributed rate limiting)
  - `psutil>=5.9.0` (for system-aware load shedding)
  - `fastapi>=0.100.0` (for FastAPI integration)
  - `sanic>=23.0.0` (for Sanic integration)
  - `aiohttp>=3.8.0` (for aiohttp integration)

</details>

### Design Philosophy

1. **Async-First**: Built from the ground up for Python's asyncio
2. **Fail-Safe Defaults**: Components fail open to preserve availability
3. **Modular**: Use only what you need, no unnecessary dependencies
4. **Type-Safe**: Full type hints (PEP 484) for better IDE support
5. **Production-Ready**: Thread-safe with proper async locking
6. **Observable**: Rich metrics and statistics for monitoring

<details>
<summary><b>📊 Comparison with Other Libraries</b></summary>

| Feature | aioresilience | pybreaker | circuitbreaker |
|---------|--------------|-----------|----------------|
| Async-native | Yes | No | No |
| Type hints | Yes | Partial | No |
| Circuit breaker | Yes | Yes | Yes |
| Retry with backoff | Yes | No | No |
| Timeout/Deadline | Yes | No | No |
| Bulkhead | Yes | No | No |
| Fallback | Yes | No | No |
| Rate limiting | Yes | No | No |
| Load shedding | Yes | No | No |
| Backpressure | Yes | No | No |
| Modular design | Yes | No | No |
| Metrics & monitoring | Yes | Basic | Basic |

</details>

## Performance

aioresilience is designed for minimal overhead in production environments. All patterns use efficient async primitives and lock-free algorithms where possible.

**Recent Optimizations:**
- Lazy event emission (only when listeners registered)
- Conditional logging (format strings only when enabled)
- O(1) path exclusions using set lookups
- Cached listener checks (reduces per-request overhead)
- Thread-safe state management with async locks

**Benchmark Your Own System:**

```bash
# Sequential overhead (baseline)
python benchmarks/benchmark_sequential.py

# Concurrent overhead (realistic load)
python benchmarks/benchmark_concurrent.py

# With contention and failures
python benchmarks/benchmark_concurrent.py --with-failures
```

See [`benchmarks/`](benchmarks/) directory for detailed benchmarking tools and methodology.

**Design Goals:**
- Microsecond-level overhead per operation
- Minimal allocations and GC pressure  
- Lock-free designs where possible
- Efficient async/await integration
- Support for 20,000+ requests/second in production APIs

## Roadmap

### Completed in v0.1.0
* Circuit Breaker pattern
* Retry policies with exponential backoff and jitter
* Bulkhead pattern for resource isolation
* Time limiters with timeout and deadline support
* Fallback mechanisms with chained fallbacks
* Rate limiting (local and distributed)
* Load shedding (basic and system-aware)
* Backpressure management
* Adaptive concurrency limiting
* Event system with local and global handlers
* FastAPI integration with modular middleware
* Sanic integration
* aiohttp integration

### Planned for Future Releases
* Cache pattern with TTL and invalidation
* Request deduplication
* Prometheus metrics exporter
* OpenTelemetry integration
* Grafana dashboard templates
* Enhanced event streaming
* WebSocket support
* HTTP client wrapper with built-in resilience
* gRPC interceptors

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

For major changes, please open an issue first to discuss what you would like to change.

<details>
<summary><b>🛠️ Development Setup (click to expand)</b></summary>

```bash
# Clone the repository
git clone https://github.com/xonming/aioresilience.git
cd aioresilience

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with all dependencies
pip install -e ".[dev]"
# or
pip install -r requirements-dev.txt

# Run tests
pytest

# Run tests with coverage
pytest --cov=aioresilience --cov-report=html

# Code formatting
black aioresilience tests
isort aioresilience tests

# Type checking
mypy aioresilience

# Linting
flake8 aioresilience
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_circuit_breaker.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=aioresilience
```

</details>

## License

Copyright 2025 aioresilience contributors

Licensed under the MIT License.
You may obtain a copy of the License at

    https://opensource.org/licenses/MIT

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and limitations under the License.

## Acknowledgments

Special thanks to:

* [aiolimiter](https://github.com/mjpieters/aiolimiter) for async rate limiting primitives

## Support

* **Documentation**: This README and Python docstrings
* **Issues**: [GitHub Issues](https://github.com/xonming/aioresilience/issues)
* **Discussions**: [GitHub Discussions](https://github.com/xonming/aioresilience/discussions)
* **PyPI**: [aioresilience on PyPI](https://pypi.org/project/aioresilience/)

---

**Built for the Python asyncio community**
