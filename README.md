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

aioresilience is a fault tolerance library for Python's asyncio ecosystem. It provides 9 resilience patterns (Circuit Breaker, Retry, Timeout, Bulkhead, Fallback, Rate Limiter, Load Shedder, Backpressure, Adaptive Concurrency) with event-driven monitoring and framework integrations for FastAPI, Sanic, and aiohttp. Use it to build reliable async applications that gracefully handle failures.

**Requirements:** Python 3.9+

**Current version:** 0.2.1 (instance-based decorators + config-based API)

```python
from aioresilience import (
    CircuitBreaker, CircuitConfig,
    RateLimiter,
    LoadShedder, LoadSheddingConfig,
    with_circuit_breaker, with_load_shedding
)

# Create pattern instances with Config API (v0.2.0+)
circuit = CircuitBreaker(
    name="backendService",
    config=CircuitConfig(failure_threshold=5, recovery_timeout=60.0)
)
rate_limiter = RateLimiter()
load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=1000))

# Example: Your backend service call
async def call_external_api():
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()

# Option 1: Use instance-based decorators (recommended for reusable instances)
@with_circuit_breaker(circuit)
@with_load_shedding(load_shedder, priority="normal")
async def decorated_call(user_id: str):
    # Check rate limit
    if await rate_limiter.check_rate_limit(user_id, "100/minute"):
        return await call_external_api()
    else:
        raise Exception("Rate limit exceeded")

# Execute the decorated function
try:
    result = await decorated_call("user_123")
except Exception as e:
    result = "Fallback value"

# Option 2: Call directly through the instance
result = await circuit.call(call_external_api)
```

## Features

- 9 resilience patterns: Circuit Breaker, Retry, Timeout, Bulkhead, Fallback, Rate Limiter, Load Shedder, Backpressure, Adaptive Concurrency
- Config-based initialization with validation (v0.2.0+)
- Event system with local and global handlers
- Async-only implementation using asyncio primitives
- Decorator and context manager APIs
- Type annotations throughout
- Framework middleware for FastAPI, Sanic, aiohttp
- Configurable logging (silent by default)

## Documentation

Documentation is in this README and Python docstrings.

## Installation

```bash
pip install aioresilience
```

<details>
<summary><b>Optional Features (click to expand)</b></summary>

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

Resilience patterns:

* **Circuit Breaker** - Prevents cascading failures by monitoring error rates
* **Rate Limiter** - Controls request rates (local or distributed via Redis)
* **Load Shedder** - Rejects requests when system is overloaded
* **Backpressure Manager** - Flow control using high/low water marks
* **Adaptive Concurrency** - Auto-adjusts concurrency using AIMD algorithm
* **Retry Policy** - Retries with exponential/linear/constant backoff
* **Timeout Manager** - Time-bound operations with deadlines
* **Bulkhead** - Resource isolation with concurrency limits
* **Fallback Handler** - Alternative responses on failure
* **Event System** - Monitoring via local and global event handlers

### Framework Integrations

Framework support:

* **FastAPI / Starlette** - Middleware and dependency injection
* **Sanic** - Middleware and decorators
* **aiohttp** - Middleware and decorators

See [INTEGRATIONS.md](INTEGRATIONS.md) for integration guides.

## Resilience Patterns

| Name | How Does It Work? | Description |
|------|-------------------|-------------|
| **Circuit Breaker** | Blocks calls after threshold | Monitors error rates and opens circuit when threshold exceeded. Prevents cascading failures. |
| **Retry** | Retries with backoff | Retries failed operations with exponential, linear, or constant backoff. Supports jitter. |
| **Timeout** | Time-bound operations | Sets maximum execution time. Supports relative timeouts and absolute deadlines. |
| **Bulkhead** | Resource isolation | Limits concurrent access to prevent resource exhaustion. Isolates failures to pools. |
| **Fallback** | Alternative responses | Provides fallback values or functions when primary operation fails. Supports chaining. |
| **Rate Limiter** | Request rate control | Limits requests per time window (second/minute/hour/day). Local or distributed (Redis). |
| **Load Shedder** | Request rejection | Rejects requests when system load exceeds thresholds. Supports CPU/memory metrics. |
| **Backpressure Manager** | Flow control | Signals upstream to slow down using high/low water marks. |
| **Adaptive Concurrency** | Dynamic limits | Adjusts concurrency based on success rate using AIMD algorithm (TCP-like). |

*Above table is inspired by [Polly: resilience policies](https://github.com/App-vNext/Polly#resilience-policies) and [resilience4j](https://github.com/resilience4j/resilience4j).*

## Logging Configuration

<details>
<summary><b>Logging Setup (click to expand)</b></summary>

aioresilience uses a `NullHandler` by default, emitting no logs. Configure logging as needed.

### Default Behavior

No logs are emitted by default:

```python
from aioresilience import CircuitBreaker

circuit = CircuitBreaker("api")  # Silent
```

### Standard Python Logging

Enable standard Python logging:

```python
import logging
from aioresilience import configure_logging

# Enable logging
configure_logging(logging.DEBUG)

circuit = CircuitBreaker("api")
```

### Custom Logging Frameworks

Integrate with loguru, structlog, or other frameworks:

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
from aioresilience.config import CircuitConfig

circuit = CircuitBreaker(
    name="backendName",
    config=CircuitConfig(
        failure_threshold=5,      # Open after 5 consecutive failures
        recovery_timeout=60.0,    # Wait 60 seconds before trying half-open
        success_threshold=2       # Need 2 successes to close from half-open
    )
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

# Or use instance-based decorator (recommended)
@with_circuit_breaker(circuit)
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

<details>
<summary><b>Monitoring Rate Limits</b></summary>

**Event-Driven Monitoring**

Track rate limit violations and allowed requests:

```python
from aioresilience import RateLimiter

rate_limiter = RateLimiter(name="api")

# Monitor allowed requests
@rate_limiter.events.on("rate_limit_passed")
async def on_passed(event):
    print(f"Request allowed for key: {event.metadata['key']}")
    print(f"Rate: {event.metadata['rate']}")

# Alert on rate limit violations
@rate_limiter.events.on("rate_limit_exceeded")
async def on_exceeded(event):
    key = event.metadata['key']
    rate = event.metadata['rate']
    print(f"Rate limit exceeded for {key} (limit: {rate})")
    # Track abusive users
    await track_rate_limit_violation(key)
```

**Polling Metrics**

```python
# For dashboards
stats = rate_limiter.get_stats()
print(f"Active limiters: {stats['active_limiters']}")
print(f"Total checks: {stats['total_checks']}")
```

</details>

### Load Shedding

There are two load shedding implementations.

#### BasicLoadShedder

The following example shows how to shed load based on request count using the Config API:

```python
from aioresilience import LoadShedder
from aioresilience.config import LoadSheddingConfig

# Create a LoadSheddingConfig and LoadShedder
ls_config = LoadSheddingConfig(
    max_requests=1000,       # Maximum concurrent requests
    max_queue_depth=500      # Maximum queue depth
)
load_shedder = LoadShedder(config=ls_config)

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
from aioresilience.config import LoadSheddingConfig

# Create a system-aware load shedder using the Config API
ls_config = LoadSheddingConfig(
    max_requests=1000,
    max_queue_depth=500,
)
load_shedder = SystemLoadShedder(config=ls_config)

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

<details>
<summary><b>Monitoring Load Shedding</b></summary>

**Event-Driven Monitoring**

Track accepted and rejected requests:

```python
from aioresilience import LoadShedder
from aioresilience.config import LoadSheddingConfig

load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=1000))

# Monitor accepted requests
@load_shedder.events.on("request_accepted")
async def on_accepted(event):
    active = event.metadata['active_requests']
    max_requests = event.metadata['max_requests']
    print(f"Request accepted ({active}/{max_requests} active)")

# Alert when shedding load
@load_shedder.events.on("request_shed")
async def on_shed(event):
    print(f"Request shed - system overloaded!")
    print(f"Active: {event.metadata['active_requests']}")
    print(f"CPU: {event.metadata.get('cpu_percent', 'N/A')}%")
    await send_alert("Load shedding active - system under pressure")
```

**Polling Metrics**

```python
# For dashboards
stats = load_shedder.get_stats()
print(f"Active requests: {stats['active_requests']}/{stats['max_requests']}")
print(f"Total shed: {stats['total_shed']}")
print(f"Shed rate: {stats['shed_rate']:.2%}")
```

</details>

### Backpressure Management

Control flow in async processing pipelines using water marks:

```python
from aioresilience import BackpressureManager
from aioresilience.config import BackpressureConfig

# Create a backpressure manager using the Config API
bp_config = BackpressureConfig(
    max_pending=1000,        # Hard limit on pending items
    high_water_mark=800,     # Start applying backpressure
    low_water_mark=200       # Stop applying backpressure
)
backpressure = BackpressureManager(config=bp_config)

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

<details>
<summary><b>Monitoring Backpressure</b></summary>

**Event-Driven Monitoring**

Track backpressure state and flow control:

```python
from aioresilience import BackpressureManager
from aioresilience.config import BackpressureConfig

bp_config = BackpressureConfig(
    max_pending=1000,
    high_water_mark=800,
    low_water_mark=200
)
backpressure = BackpressureManager(config=bp_config)

# Monitor backpressure activation
@backpressure.events.on("backpressure_high")
async def on_high(event):
    pending = event.metadata['pending_count']
    high_mark = event.metadata['high_water_mark']
    print(f"High backpressure: {pending} pending (threshold: {high_mark})")
    await signal_upstream_to_slow_down()

# Monitor backpressure relief
@backpressure.events.on("backpressure_low")
async def on_low(event):
    pending = event.metadata['pending_count']
    print(f"Backpressure relieved: {pending} pending")
    await signal_upstream_to_resume()
```

</details>

### Adaptive Concurrency Limiting

Automatically adjust concurrency limits based on observed success rates using an AIMD
(Additive Increase, Multiplicative Decrease) algorithm.

Key configuration is provided via AdaptiveConcurrencyConfig:

- initial_limit: starting concurrency
- min_limit / max_limit: hard bounds for concurrency
- increase_rate: additive increase applied when the success rate is healthy
- decrease_factor: multiplicative decrease applied when the success rate is poor
- measurement_window: number of completed requests per adjustment cycle
- success_threshold: success-rate threshold to trigger an increase (0.0–1.0)
- failure_threshold: success-rate threshold below which a decrease is triggered (0.0–1.0)

Example (recommended usage with config and async context manager):

```python
from aioresilience import AdaptiveConcurrencyLimiter
from aioresilience.config import AdaptiveConcurrencyConfig

config = AdaptiveConcurrencyConfig(
    initial_limit=100,
    min_limit=10,
    max_limit=1000,
    increase_rate=1.0,
    decrease_factor=0.9,
    measurement_window=100,
    success_threshold=0.95,
    failure_threshold=0.80,
)

limiter = AdaptiveConcurrencyLimiter("api-limiter", config)

async def handle_request():
    # This will raise RuntimeError if the limiter is at capacity
    async with limiter:
        # Only runs if a concurrency slot is acquired
        return await backend_service.do_something()
```

Manual acquire/release is also supported:

```python
config = AdaptiveConcurrencyConfig(initial_limit=100, min_limit=10, max_limit=1000)
limiter = AdaptiveConcurrencyLimiter("api-limiter", config)

async def handle_request():
    if await limiter.acquire():
        try:
            result = await backend_service.do_something()
            await limiter.release(success=True)
            return result
        except Exception:
            await limiter.release(success=False)
            raise
    else:
        raise Exception("Concurrency limit reached")
```

> The AIMD algorithm increases the limit linearly on high success rates and decreases it
> multiplicatively when the success rate drops, similar to TCP congestion control.

<details>
<summary><b>Monitoring Adaptive Concurrency</b></summary>

AdaptiveConcurrencyLimiter integrates with the event system via LoadShedderEvent.
You can subscribe to load level changes through limiter.events.

```python
from aioresilience import AdaptiveConcurrencyLimiter
from aioresilience.config import AdaptiveConcurrencyConfig
from aioresilience.events import EventType

config = AdaptiveConcurrencyConfig(initial_limit=100)
limiter = AdaptiveConcurrencyLimiter("api-limiter", config)

@limiter.events.on(EventType.LOAD_LEVEL_CHANGE.value)
async def on_load_change(event):
    print(
        f"[adaptive:{event.pattern_name}] "
        f"Limit change: {event.metadata.get('load_level')} "
        f"(active={event.metadata.get('active_requests')}, "
        f"max={event.metadata.get('max_requests')})"
    )
```

</details>

### Retry Pattern

Automatically retry failed operations with exponential backoff and jitter:

```python
from aioresilience import RetryPolicy, retry, RetryStrategy
from aioresilience.config import RetryConfig

# Using RetryPolicy with RetryConfig
policy = RetryPolicy(
    config=RetryConfig(
        max_attempts=5,
        initial_delay=1.0,
        max_delay=60.0,
        backoff_multiplier=2.0,
        strategy=RetryStrategy.EXPONENTIAL,
        jitter=0.1,
    )
)

async def fetch_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        return response.json()

# Execute with retry
result = await policy.execute(fetch_data)

# Or use instance-based decorator (recommended)
user_policy = RetryPolicy(config=RetryConfig(
    max_attempts=3,
    initial_delay=0.5,
    strategy=RetryStrategy.EXPONENTIAL
))

@with_retry(user_policy)
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

<details>
<summary><b>Monitoring Retry Attempts</b></summary>

**Event-Driven Monitoring**

Track retry attempts, successes, and exhaustion in real-time:

```python
from aioresilience import RetryPolicy
from aioresilience.config import RetryConfig

policy = RetryPolicy(config=RetryConfig(max_attempts=3))

# Monitor each retry attempt
@policy.events.on("retry_attempt")
async def on_retry(event):
    print(f"Retry attempt {event.metadata['attempt']}/{event.metadata['max_attempts']}")
    print(f"Delay: {event.metadata['delay']}s")

# Celebrate success after retries
@policy.events.on("retry_success")
async def on_success(event):
    attempts = event.metadata['attempt']
    print(f"Success after {attempts} attempts!")

# Alert when all retries exhausted
@policy.events.on("retry_exhausted")
async def on_exhausted(event):
    print(f"All {event.metadata['max_attempts']} retries failed")
    await send_alert("Retry exhausted for critical operation")
```

</details>

### Timeout Pattern

Set maximum execution time for async operations:

```python
from aioresilience import TimeoutManager, timeout, with_timeout
from aioresilience.config import TimeoutConfig

# Using TimeoutManager with TimeoutConfig
manager = TimeoutManager(config=TimeoutConfig(timeout=5.0))

async def slow_operation():
    await asyncio.sleep(10.0)
    return "result"

# Will raise OperationTimeoutError after 5 seconds
try:
    result = await manager.execute(slow_operation)
except OperationTimeoutError:
    print("Operation timed out")

# Or use instance-based decorator (recommended)
timeout_mgr = TimeoutManager(config=TimeoutConfig(timeout=3.0))

@with_timeout_manager(timeout_mgr)
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

<details>
<summary><b>Monitoring Timeouts</b></summary>

**Event-Driven Monitoring**

Track timeout events and successful completions:

```python
from aioresilience import TimeoutManager
from aioresilience.config import TimeoutConfig

manager = TimeoutManager(config=TimeoutConfig(timeout=5.0))

# Monitor successful completions
@manager.events.on("timeout_success")
async def on_success(event):
    duration = event.metadata['duration']
    print(f"Completed in {duration:.2f}s (within {event.metadata['timeout']}s limit)")

# Alert on timeouts
@manager.events.on("timeout_exceeded")
async def on_timeout(event):
    print(f"Operation timed out after {event.metadata['timeout']}s")
    await send_alert(f"Timeout exceeded for {event.pattern_name}")
```

</details>

### Bulkhead Pattern

Isolate resources and limit concurrent access:

```python
from aioresilience import Bulkhead, bulkhead
from aioresilience.config import BulkheadConfig

# Create a bulkhead for database connections using BulkheadConfig
db_bulkhead = Bulkhead(
    config=BulkheadConfig(
        max_concurrent=10,    # Max 10 concurrent database operations
        max_waiting=20,       # Max 20 requests waiting in queue
        timeout=5.0,          # Max 5 seconds wait time
    ),
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

# Or use instance-based decorator (recommended)
api_bulkhead = Bulkhead(name="api", config=BulkheadConfig(max_concurrent=5, max_waiting=10))

@with_bulkhead(api_bulkhead)
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

<details>
<summary><b>Monitoring Bulkhead</b></summary>

**Event-Driven Monitoring**

Track bulkhead capacity and rejections:

```python
from aioresilience import Bulkhead
from aioresilience.config import BulkheadConfig

bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=10, max_waiting=20), name="database")

# Monitor accepted requests
@bulkhead.events.on("bulkhead_accepted")
async def on_accepted(event):
    active = event.metadata['active_count']
    max_concurrent = event.metadata['max_concurrent']
    print(f"Request accepted ({active}/{max_concurrent} slots used)")

# Alert on rejections
@bulkhead.events.on("bulkhead_rejected")
async def on_rejected(event):
    print(f"Request rejected - bulkhead full!")
    print(f"Active: {event.metadata['active_count']}, Waiting: {event.metadata['waiting_count']}")
    await send_alert("Bulkhead capacity exceeded")
```

**Polling Metrics**

```python
# For dashboards and health checks
metrics = bulkhead.get_metrics()
print(f"Current active: {metrics['current_active']}/{metrics['max_concurrent']}")
print(f"Peak active: {metrics['peak_active']}")
print(f"Total rejected: {metrics['rejected_requests']}")
```

</details>

### Fallback Pattern

Provide alternative responses when operations fail:

```python
import httpx
from aioresilience import FallbackHandler, FallbackConfig, with_fallback_handler, chained_fallback, with_fallback

# Simple static fallback using instance-based decorator (recommended)
items_fallback = FallbackHandler(config=FallbackConfig(fallback=[]))

@with_fallback_handler(items_fallback)
async def fetch_items():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/items")
        return response.json()

# If fetch_items fails, returns empty list []

# Fallback with callable
status_fallback = FallbackHandler(config=FallbackConfig(fallback=lambda: {"status": "unavailable"}))

@with_fallback_handler(status_fallback)
async def get_service_status():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/status")
        return response.json()

# Async fallback function
async def get_cached_data(*args, **kwargs):
    # Simulated cache lookup
    return {"cached": True, "data": "cached_user_data"}

user_fallback = FallbackHandler(config=FallbackConfig(fallback=get_cached_data))

@with_fallback_handler(user_fallback)
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

<details>
<summary><b>Monitoring Fallback</b></summary>

**Event-Driven Monitoring**

Track when fallback values are used:

```python
from aioresilience import FallbackHandler, with_fallback_handler
from aioresilience.config import FallbackConfig

# Create fallback handler and register event listener
fallback_handler = FallbackHandler(config=FallbackConfig(fallback={"status": "unavailable"}))

@fallback_handler.events.on("fallback_triggered")
async def on_fallback(event):
    print(f"Fallback triggered due to: {event.metadata.get('error_type')}")
    await send_alert("Primary service failed, using fallback")

@with_fallback_handler(fallback_handler)
async def get_service_status():
    # ... implementation ...
    pass
```

</details>

#### Combining Patterns

Patterns can be stacked:

```python
from aioresilience import RetryPolicy, FallbackHandler, with_retry, with_fallback_handler
from aioresilience.config import RetryConfig, FallbackConfig

# Create pattern instances
retry_policy = RetryPolicy(config=RetryConfig(max_attempts=3, initial_delay=1.0))
fallback_handler = FallbackHandler(config=FallbackConfig(fallback={"data": [], "status": "degraded"}))

@with_retry(retry_policy)
@with_fallback_handler(fallback_handler)
async def fetch_critical_data():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/critical-data")
        response.raise_for_status()
        return response.json()
```

## Framework Integrations

Middleware and decorators are available for FastAPI, Sanic, and aiohttp. Error messages, status codes, and retry headers are configurable.

See [INTEGRATIONS.md](INTEGRATIONS.md) for details.

### FastAPI Integration

Middleware and decorators for FastAPI:

```python
from fastapi import FastAPI
from aioresilience import CircuitBreaker, LoadShedder, RetryPolicy
from aioresilience.config import CircuitConfig, LoadSheddingConfig
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

# Circuit Breaker
app.add_middleware(
    CircuitBreakerMiddleware,
    circuit_breaker=CircuitBreaker(name="api", config=CircuitConfig(failure_threshold=5)),
    error_message="Service temporarily down",
    status_code=503,
    retry_after=30,
    include_circuit_info=False,
    exclude_paths={"/health", "/metrics"},
)

# Load Shedding
app.add_middleware(
    LoadSheddingMiddleware,
    load_shedder=LoadShedder(config=LoadSheddingConfig(max_requests=1000)),
    error_message="Too busy - please retry",
    retry_after=10,
    priority_header="X-Request-Priority",
    default_priority="normal",
)

# Timeout
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

# Retry (route-level decorator)
@app.get("/api/data")
@retry_route(RetryPolicy(max_attempts=3, initial_delay=1.0))
async def get_data():
    return {"data": "..."}
```

### Rate Limiting Dependency

```python
from fastapi import FastAPI, Depends
from aioresilience import RateLimiter
from aioresilience.integrations.fastapi import rate_limit_dependency

app = FastAPI()
rate_limiter = RateLimiter(name="api")

@app.get("/api/data", dependencies=[
    Depends(rate_limit_dependency(rate_limiter, "100/minute"))
])
async def get_data():
    return {"data": "..."}

# With custom configuration
@app.get("/api/premium", dependencies=[
    Depends(rate_limit_dependency(
        rate_limiter,
        "1000/minute",
        error_message="Premium tier limit exceeded",
        status_code=429,
        retry_after=30,
        key_func=lambda req: req.headers.get("X-User-ID"),
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

Middleware and decorators for Sanic:

```python
from sanic import Sanic, json
from aioresilience import CircuitBreaker, RateLimiter, LoadShedder
from aioresilience.config import LoadSheddingConfig
from aioresilience.integrations.sanic import (
    setup_resilience,
    circuit_breaker_route,
    rate_limit_route,
    timeout_route,
    bulkhead_route,
)

app = Sanic("MyApp")

# Global resilience setup
setup_resilience(
    app,
    circuit_breaker=CircuitBreaker(name="api"),
    rate_limiter=RateLimiter(name="api"),
    rate="1000/minute",
    load_shedder=LoadShedder(config=LoadSheddingConfig(max_requests=500)),
    timeout=30.0,
    exclude_paths={"/health", "/metrics", "/admin"},
    circuit_error_message="API temporarily unavailable",
    circuit_status_code=503,
    circuit_retry_after=60,
    rate_error_message="Too many requests",
    rate_retry_after=120,
    load_error_message="Server overloaded",
    priority_header="X-Priority",
)

# Route decorators
@app.get("/api/data")
@circuit_breaker_route(
    CircuitBreaker(name="api"),
    error_message="Service down",
    status_code=503,
    retry_after=30,
    include_info=False,
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

Middleware and decorators for aiohttp:

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

# Add resilience middleware
from aioresilience.config import CircuitConfig, LoadSheddingConfig

app.middlewares.append(create_resilience_middleware(
    circuit_breaker=CircuitBreaker(name="api", config=CircuitConfig()),
    rate_limiter=RateLimiter(name="api"),
    rate="1000/minute",
    load_shedder=LoadShedder(config=LoadSheddingConfig(max_requests=500)),
    timeout=30.0,
    exclude_paths={"/health", "/metrics"},
    circuit_error_message="API down",
    circuit_status_code=503,
    circuit_retry_after=45,
    rate_error_message="Limit reached",
    rate_retry_after=90,
    load_error_message="Too busy",
    priority_header="X-Priority",
))

# Handler decorators
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

See [INTEGRATIONS.md](INTEGRATIONS.md) for more details.

## Event System

Patterns emit events for logging, monitoring, and metrics. Event handlers can be local (per pattern) or global (centralized).

### Local Event Handlers

Each pattern has an `EventEmitter` via the `.events` attribute:

```python
from aioresilience import CircuitBreaker
import logging

logger = logging.getLogger(__name__)

circuit = CircuitBreaker(name="backend", config=CircuitConfig(failure_threshold=5))

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
    logger.critical(f"Circuit {event.name} OPENED! System degraded.")

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
from aioresilience.config import CircuitConfig, BulkheadConfig

circuit = CircuitBreaker(name="api", config=CircuitConfig())
rate_limiter = RateLimiter(name="api")
bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=100))
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
<summary><b>Project Structure (click to expand)</b></summary>

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

1. **Async-First**: Built for Python's asyncio
2. **Fail-Safe Defaults**: Components fail open to preserve availability
3. **Modular**: Use only what you need, no unnecessary dependencies
4. **Type-Safe**: Full type hints (PEP 484)
5. **Thread-Safe**: Proper async locking
6. **Observable**: Metrics and statistics for monitoring

<details>
<summary><b>Comparison with Other Libraries</b></summary>

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

Design characteristics:

- **Efficient async/await integration** - Native asyncio support throughout
- **Smart caching** - Coroutine detection and listener lookups are cached
- **Lock optimization** - Events emitted outside locks to reduce contention
- **Lazy evaluation** - Work only happens when needed (e.g., events only emit with listeners)
- **O(1) operations** - Path exclusions use precomputed sets in middleware
- **Silent by default** - Zero logging overhead unless explicitly enabled

All optimizations are transparent with no breaking API changes.

## Exception Handling (v0.2.0)

Exception handling with callbacks, context, and custom exception types.

### ExceptionConfig

Configuration for exception handling:

```python
from aioresilience import CircuitBreaker, CircuitConfig, ExceptionConfig
from aioresilience.exceptions import ExceptionContext, CircuitBreakerReason

def on_failure(ctx: ExceptionContext):
    """Callback invoked when circuit breaker encounters a failure"""
    print(f"Pattern: {ctx.pattern_name}")
    print(f"Type: {ctx.pattern_type}")
    print(f"Reason: {ctx.reason.name}")  # CALL_FAILED or THRESHOLD_EXCEEDED
    print(f"Exception: {ctx.original_exception}")
    print(f"Metadata: {ctx.metadata}")
    
    # Take action based on reason
    if ctx.reason == CircuitBreakerReason.THRESHOLD_EXCEEDED:
        send_alert(f"Circuit {ctx.pattern_name} opened!")
    elif ctx.reason == CircuitBreakerReason.CALL_FAILED:
        log_failure(ctx.original_exception)

# Configure exception handling
exc_config = ExceptionConfig(
    on_exception=on_failure,  # Callback for all failures
    handled_exceptions=(ValueError, TypeError),  # Only handle these types
    exception_predicate=lambda e: "timeout" not in str(e),  # Custom filter
)

circuit = CircuitBreaker(
    name="api",
    config=CircuitConfig(failure_threshold=5),
    exceptions=exc_config
)

# Callback is invoked automatically on failures
try:
    result = await circuit.call(risky_operation)
except Exception as e:
    pass  # Callback already handled it
```

### ExceptionContext

Context object passed to exception callbacks:

| Field | Type | Description |
|-------|------|-------------|
| `pattern_name` | str | Name of the pattern instance |
| `pattern_type` | str | Type of pattern ("circuit_breaker", "retry", etc.) |
| `reason` | IntEnum | Reason code for the failure |
| `original_exception` | Exception \| None | The original exception that occurred |
| `metadata` | dict | Pattern-specific context (state, counts, etc.) |

### Reason Codes

Each pattern provides specific reason codes:

**CircuitBreakerReason:**
- `CIRCUIT_OPEN` (0) - Circuit is in OPEN state
- `TIMEOUT` (1) - Operation timed out
- `HALF_OPEN_REJECTION` (2) - Half-open state rejecting calls
- `CALL_FAILED` (3) - Normal failure during operation
- `THRESHOLD_EXCEEDED` (4) - Failure threshold exceeded, circuit opening

**BulkheadReason:**
- `CAPACITY_FULL` (0) - Max concurrent slots occupied
- `QUEUE_FULL` (1) - Waiting queue is full
- `TIMEOUT` (2) - Timeout while waiting for slot

See `aioresilience.exceptions.reasons` for all reason codes.

### Custom Exception Types

Transform or replace exceptions:

```python
class ServiceUnavailable(Exception):
    """Custom exception for service failures"""
    pass

exc_config = ExceptionConfig(
    exception_type=ServiceUnavailable,  # Raise this instead
    on_exception=log_failure
)

circuit = CircuitBreaker(name="api", config=CircuitConfig(), exceptions=exc_config)

try:
    await circuit.call(operation)
except ServiceUnavailable:  # Catch your custom exception
    print("Service unavailable!")
```

## Roadmap

### Completed in v0.2.0
* Config API for type-safe configuration
* Exception handling system with callbacks and context
* Type-safe event system with enum-based states
* Async-only API (removed broken sync methods)
* Middleware error handling

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
* Event streaming
* WebSocket support
* HTTP client wrapper
* gRPC interceptors

## Contributing

Contributions are welcome. Please submit a Pull Request.

For major changes, open an issue first to discuss the change.

<details>
<summary><b>Development Setup (click to expand)</b></summary>

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
