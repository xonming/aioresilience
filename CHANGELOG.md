# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned Features
- Django integration
- Flask integration
- Prometheus metrics exporter
- OpenTelemetry integration

## [0.2.0] - 2025-11-07

### Added

#### Config API (Breaking Change)
- **Type-Safe Configuration Objects** - All resilience patterns now use dedicated Config classes
  - `CircuitConfig` for Circuit Breaker configuration
  - `BulkheadConfig` for Bulkhead configuration
  - `LoadSheddingConfig` for Load Shedder configuration
  - `BackpressureConfig` for Backpressure Manager configuration
  - `RetryConfig` for Retry Policy configuration
  - Pydantic-based validation for all configuration parameters
  - Clear separation between pattern configuration and exception handling configuration
  - Example: `CircuitBreaker(name="api", config=CircuitConfig(failure_threshold=5))`

#### Event System Improvements
- **Type-Safe Event States** - Events now use enum objects instead of strings
  - `CircuitBreakerEvent` uses `CircuitState` enum instead of string states
  - Serialization to strings happens only in `to_dict()` method
  - Type-safe event comparisons: `event.old_state == CircuitState.CLOSED`
  - Prevents string typos and enables IDE autocompletion

#### Exception Handling System
- **ExceptionConfig API** - Unified exception configuration for all patterns
  - `ExceptionConfig(on_exception=callback)` - Register failure callbacks
  - `exception_type` - Custom exception class to raise
  - `exception_transformer` - Transform exceptions with custom logic
  - `handled_exceptions` - Tuple of exception types to catch
  - `exception_predicate` - Filter function for conditional handling
  - Works with Circuit Breaker, Retry, Bulkhead, and all patterns
  - Example: `ExceptionConfig(on_exception=log_failure, exception_type=CustomError)`

- **ExceptionContext** - Context object passed to callbacks
  - `pattern_name` - Name of the pattern instance
  - `pattern_type` - Type of pattern (e.g., "circuit_breaker")
  - `reason` - Reason code (IntEnum) for the failure
  - `original_exception` - The original exception that occurred
  - `metadata` - Dict with pattern-specific context (state, failure_count, etc.)
  - Example: Access via `def callback(ctx: ExceptionContext): print(ctx.metadata['state'])`

- **CircuitBreakerReason Enum Additions**
  - `CALL_FAILED` (3) - Normal failure during operation
  - `THRESHOLD_EXCEEDED` (4) - Failure threshold exceeded, circuit opening
  - Context-aware: Circuit provides appropriate reason based on state transition
  - Enables intelligent error handling: different actions for different failure types

- **Proper Callback Invocation** - Fixed broken callback system
  - Callbacks now correctly invoked when exceptions occur
  - Supports both sync and async callback functions
  - Circuit breaker tracks old_state to detect transitions
  - Provides proper reason codes based on context:
    - `THRESHOLD_EXCEEDED` when circuit transitions to OPEN
    - `CALL_FAILED` for normal operation failures
  - Callbacks receive full context including state, failure_count, etc.

- **5xx Response Handling in Middleware**
  - FastAPI CircuitBreakerMiddleware now converts 5xx responses to exceptions
  - Enables circuit breaker to properly track downstream service failures
  - Without this, circuit breaker would never see failures (middleware swallowed them)
  - Proper callback invocation for HTTP error responses
  - Example: Backend returns 500 → converted to exception → circuit breaker tracks it

- **No More Silent Errors** - Eliminated all silent exception handling
  - Before: `except Exception: pass` - errors disappeared silently
  - After: `except Exception as e: logger.error(f"Error: {e}")` - all errors logged
  - Callback errors logged with full context and stack trace
  - Exception handler errors logged but don't break main flow
  - Error visibility for debugging
  - Example log: `"Circuit breaker 'api': Error in on_exception callback: AttributeError: 'NoneType' has no attribute 'value'"`

- **ExceptionHandler Class** - Base exception handling for all patterns
  - `should_handle_exception(exc)` - Check if exception should be handled
  - `handle_exception(reason, exc, message)` - Process and transform exceptions
  - `_create_exception(context, message)` - Factory for creating exceptions
  - Used by all resilience patterns for consistent exception handling
  - Supports exception transformation and custom exception types

#### Testing
- **Middleware Tests** - Added 16 new integration tests
  - 8 tests for FastAPI Bulkhead middleware
  - 8 tests for FastAPI Circuit Breaker middleware

### Changed

#### Breaking Changes
- **Async-Only API**
  - Removed all sync methods:
    - `call_sync()` (was broken and not thread-safe)
    - `_raise_circuit_open_error_sync()`
  - Decorator now raises `TypeError` for non-async functions with a clear error message:
    - "Circuit breaker decorator can only be applied to async functions"
- **Config API Required**
  - All patterns now use configuration objects in `aioresilience.config` for initialization.
  - Old:
    - `CircuitBreaker(name="api", failure_threshold=5)` ❌
  - New:
    - `CircuitBreaker(name="api", config=CircuitConfig(failure_threshold=5))` ✅
  - Provides type safety, validation, and consistent initialization.
- **AdaptiveConcurrencyLimiter API (Standardized)**
  - Switched to the same config-based pattern as other components.
  - Old:
    - `AdaptiveConcurrencyLimiter(initial_limit=100, min_limit=10, max_limit=1000, ...)`
  - New:
    - `AdaptiveConcurrencyLimiter("api-limiter", AdaptiveConcurrencyConfig(initial_limit=100, min_limit=10, max_limit=1000, ...))`
  - Added async context manager support:
    - `async with limiter: ...` will acquire/release with AIMD updates.
  - Introduced and documented:
    - `success_threshold` and `failure_threshold` parameters controlling when the AIMD
      algorithm increases or decreases the concurrency limit.
  - All old-style positional init examples are deprecated and removed from docs.

#### Event System
- **Dual Lookup Support** - EventEmitter now supports both enum values and string names
  - Handlers can be registered with either `EventType.RETRY_EXHAUSTED.value` or `"retry_exhausted"`
  - Internal optimization: handlers looked up by both enum value and lowercase string name
  - Backward compatible with string-based registrations
  - Use enum values for performance

### Fixed
- **Circuit Breaker Middleware** - Fixed exception handling in FastAPI middleware
  - Middleware now properly returns 503 when circuit opens
  - Fixed race condition in circuit state checking
  - Proper handling of `CircuitBreakerOpenError`
- **Callback Invocation** - Fixed `on_exception` callback not being called
  - Added proper `ExceptionContext` creation in circuit breaker
  - Callbacks now invoked for all handled exceptions
  - Works correctly in both sync and async callback functions
- **Event State Serialization** - Fixed inconsistent state representation
  - Events use enums internally, serialize to lowercase strings in `to_dict()`
  - Consistent state names across all events
- **System Load Shedding Tests** - Fixed type assertions
  - Changed from `load_level.value == "normal"` to `load_level.name.lower() == "normal"`
  - Tests now properly verify enum state

### Documentation
- **Updated README for v0.2.0** - Reflects new Config API and features
  - Updated all examples to use Config API
  - Documented async-only requirement
  - Added version 0.2.0 highlights
- **Fixed Event System Documentation** - Replaced outdated polling-based examples with correct event-driven system
  - Updated "Event Consumption" section to show proper event handlers
  - Added examples of local event handlers with `@pattern.events.on()` decorator
  - Added examples of global event bus for centralized monitoring
  - Documented all event types by pattern
  - Added wildcard event handler examples

### Performance

- **Core Optimizations**
  - Circuit Breaker:
    - Lazy event emission (only emit when listeners are present).
    - Event emissions moved outside of locks to reduce contention.
    - Cached coroutine/function checks to avoid repeated `iscoroutinefunction()` calls.
  - Retry Policy:
    - Cached coroutine detection and reduced per-attempt allocations.
  - Event System:
    - Cached listener lookups and efficient handler dispatch paths.
  - Middleware/Integrations:
    - O(1) path exclusions using precomputed sets.
- **Logging Architecture**
  - Centralized in `aioresilience.logging`:
    - Library is silent by default using `NullHandler`, following Python best practices.
    - `configure_logging()` enables standard logging in one call.
    - `set_error_handler()` allows integration with loguru, structlog, or any custom sink.
  - Internal logging uses centralized configuration and error handler mechanism.
- **Code Reduction**
  - Removed broken sync methods and legacy paths to keep hot code paths lean.
  - Total statements reduced while improving behavior and observability.

### Removed
- **Sync Methods** - All synchronous methods removed (BREAKING)
  - `call_sync()` - Not thread-safe
  - `_raise_circuit_open_error_sync()` - No longer needed
  - Sync decorator wrapper - Use async functions only
- **Integration Benchmarks** - Moved to separate repository

## Migration Guide v0.1.0 → v0.2.0

### Required Changes

#### 1. Update Pattern Initialization (Config API)

```python
# v0.1.0 (Old)
from aioresilience import CircuitBreaker, Bulkhead, LoadShedder

circuit = CircuitBreaker(name="api", failure_threshold=5, recovery_timeout=60.0)
bulkhead = Bulkhead(name="db", max_concurrent=10)
shedder = LoadShedder(max_requests=1000)

# v0.2.0 (New)
from aioresilience import (
    CircuitBreaker, CircuitConfig,
    Bulkhead, BulkheadConfig,
    LoadShedder, LoadSheddingConfig
)

circuit = CircuitBreaker(
    name="api",
    config=CircuitConfig(failure_threshold=5, recovery_timeout=60.0)
)
bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=10))
shedder = LoadShedder(config=LoadSheddingConfig(max_requests=1000))
```

#### 2. Remove Sync Function Decorators

```python
# v0.1.0 (Old) - This worked but was broken
@circuit_breaker("api", failure_threshold=3)
def sync_function():  # Sync function
    return requests.get("https://api.example.com")

# v0.2.0 (New) - Must be async
@circuit_breaker("api", failure_threshold=3)
async def async_function():  # Async function required
    async with httpx.AsyncClient() as client:
        return await client.get("https://api.example.com")
```

#### 3. Use ExceptionConfig for Callbacks (New Feature)

```python
# v0.2.0 - Exception handling with callbacks
from aioresilience import CircuitBreaker, CircuitConfig, ExceptionConfig
from aioresilience.exceptions import ExceptionContext

def on_failure(ctx: ExceptionContext):
    """Called when circuit breaker encounters a failure"""
    print(f"Failure in {ctx.pattern_name}")
    print(f"Reason: {ctx.reason.name}")  # CALL_FAILED or THRESHOLD_EXCEEDED
    print(f"State: {ctx.metadata['state']}")
    print(f"Failure count: {ctx.metadata['failure_count']}")
    
    # Send alert if circuit opened
    if ctx.reason.name == 'THRESHOLD_EXCEEDED':
        send_alert(f"Circuit {ctx.pattern_name} opened!")

exc_config = ExceptionConfig(on_exception=on_failure)
circuit = CircuitBreaker(
    name="api",
    config=CircuitConfig(failure_threshold=5),
    exceptions=exc_config
)

# Now whenever the circuit fails, on_failure callback is invoked
try:
    await circuit.call(risky_operation)
except Exception:
    pass  # Callback already logged the failure
```

#### 4. Update Event Comparisons (Optional but Recommended)

```python
# v0.1.0 (Old) - String comparisons
@circuit.events.on("state_change")
async def handler(event):
    if event.old_state == "closed" and event.new_state == "open":
        print("Circuit opened!")

# v0.2.0 (New) - Type-safe enum comparisons
from aioresilience.circuit_breaker import CircuitState

@circuit.events.on(EventType.STATE_CHANGE.value)  # More efficient
async def handler(event):
    if event.old_state == CircuitState.CLOSED and event.new_state == CircuitState.OPEN:
        print("Circuit opened!")
```

### Benefits of Upgrading

- Type safety: Pydantic validation catches configuration errors early
- IDE support: Autocomplete and type hints for all config options
- API: Clear separation between configuration and behavior
- Removed broken sync methods
- Optimized event emission
- Error handling: All errors logged

### Backward Compatibility

- ✅ **Event handlers**: String-based event registration still works
- ✅ **RateLimiter**: No Config API required (backward compatible)
- ⚠️ **Breaking**: Config API required for Circuit Breaker, Bulkhead, LoadShedder, Backpressure, Retry
- ⚠️ **Breaking**: Sync functions no longer supported with decorators

## [0.1.0] - 2025-11-06

### Added

#### Core Features

- **Error Handling Improvements**
  - Renamed `TimeoutError` to `OperationTimeoutError` to avoid collision with Python builtin
  - Added catch-all exception handler in CircuitBreaker to ensure all failures are tracked
  - Fixed Bulkhead race condition in `_waiting_count` management
  - Protected event emissions in finally blocks with exception handling
  - Added input validation to CircuitBreaker (name, thresholds, timeouts)
  - Standardized error message formatting across all patterns
  - Resource cleanup even if event handlers fail

- **Event System** [NEW]
  - Event-driven observability for all resilience patterns
  - Local event handlers via `EventEmitter` per pattern instance
  - Global event bus for centralized monitoring across all patterns
  - Wildcard handlers (`"*"`) to capture all events
  - Thread-safe async event emission with `asyncio.gather`
  - Event types: `CircuitBreakerEvent`, `RetryEvent`, `TimeoutEvent`, `FallbackEvent`, `BulkheadEvent`, `RateLimitEvent`, `LoadShedderEvent`
  - Event data includes timestamps, pattern state, metadata, and context
  - Decorator syntax for handler registration: `@circuit.events.on("state_change")`
  - Example file: `examples/events_example.py`

- **Circuit Breaker Pattern**
  - Async-first implementation with CLOSED, OPEN, and HALF_OPEN states
  - Automatic failure detection and recovery
  - Configurable failure threshold, recovery timeout, and success threshold
  - Metrics tracking (total requests, failures, success rate, consecutive failures)
  - Global circuit breaker manager for centralized management
  - Decorator support (`@circuit_breaker`)
  - Thread-safe implementation with proper async locking
  - Manual reset capability

- **Rate Limiting**
  - Local (in-memory) rate limiter using aiolimiter
  - Distributed Redis-based rate limiter with sliding window algorithm
  - Support for multiple time periods (second, minute, hour, day)
  - Per-key rate limiting (e.g., per user, per IP)
  - Fail-open behavior for resilience
  - LRU cache with configurable max size to prevent memory leaks
  - Atomic operations for thread safety

- **Load Shedding**
  - BasicLoadShedder with request count and queue depth limits
  - SystemLoadShedder with CPU and memory monitoring (requires psutil)
  - Priority-based request handling (high, normal, low)
  - Load level calculation (NORMAL, ELEVATED, HIGH, CRITICAL)
  - Queue depth management
  - Decorator support (`@with_load_shedding`)
  - Real-time statistics and metrics

- **Backpressure Management**
  - Water mark-based flow control (high/low water marks)
  - Event-driven backpressure signaling using asyncio.Event
  - Timeout support for acquire operations
  - Pending request tracking
  - Automatic activation/deactivation based on load
  - Decorator support (`@with_backpressure`)

- **Adaptive Concurrency Limiting**
  - AIMD (Additive Increase Multiplicative Decrease) algorithm
  - Automatic concurrency adjustment based on success rate
  - Configurable min/max limits
  - Configurable increase rate and decrease factor
  - Success rate measurement windows
  - Real-time statistics

- **Framework Integrations**
  - FastAPI middleware for load shedding (LoadSheddingMiddleware)
  - FastAPI dependency for rate limiting (rate_limit_dependency)
  - Client IP extraction with proxy support (X-Forwarded-For, X-Real-IP)
  - Automatic HTTP 503/429 responses with Retry-After headers

- **Developer Experience**
  - Full type hints (PEP 484) for all public APIs
  - Docstrings with examples
  - Decorator patterns for all major features
  - Error messages and structured logging
  - py.typed marker for type checker support
  - Modular design with optional dependencies

### Fixed

#### Critical Bug Fixes
- **CircuitBreaker Thread Safety**
  - Made `can_execute()` async and added lock protection
  - Made `on_success()` and `on_failure()` async with lock protection
  - Fixed race conditions in state transitions (OPEN → HALF_OPEN → CLOSED)
  - Proper reset of `half_open_calls` counter during state transitions
  - Removed redundant state tracking variables (`failure_count`, `last_failure_time`)
  - Added proper lock protection in `reset()` method
  - Updated `call()` method to use async state management

- **LocalRateLimiter Race Condition**
  - Fixed race condition in `check_rate_limit()` by using atomic acquire
  - Replaced `has_capacity()` check with direct `acquire()` with timeout=0
  - Prevents race condition where capacity check passes but acquire fails

- **LocalRateLimiter Memory Leak**
  - Implemented LRU cache with configurable max size (default: 10000)
  - Added OrderedDict for efficient LRU eviction
  - Cleanup of least recently used limiters
  - Added lock protection for limiter dictionary access
  - Prevents unbounded memory growth with many unique keys

- **FastAPI Integration**
  - Fixed middleware to return JSONResponse instead of raising HTTPException
  - Updated `rate_limit_dependency` documentation with correct class names
  - Changed from `AsyncRateLimiter` (non-existent) to `RateLimiter`
  - Added proper HTTP status code constants (HTTP_429_TOO_MANY_REQUESTS)
  - Improved error response format

### Changed

#### Breaking Changes
- **TimeoutError → OperationTimeoutError** (BREAKING)
  - Custom `TimeoutError` renamed to `OperationTimeoutError` to avoid collision with Python builtin
  - Migration: Replace all `from aioresilience import TimeoutError` with `from aioresilience import OperationTimeoutError`
  - No behavioral changes - exception works identically
  - Python's builtin `TimeoutError` now accessible without name collision

#### API Changes
- **CircuitBreaker**
  - `can_execute()` is now async (breaking change for sync usage)
  - `on_success()` is now async
  - `on_failure()` is now async
  - `call_sync()` now emits deprecation warning (not thread-safe)
  - Simplified metrics structure (removed duplicate fields)

- **LocalRateLimiter**
  - Added `max_limiters` parameter to `__init__` (default: 10000)
  - Added `_lock` for thread-safe limiter dictionary access
  - Changed internal storage from `Dict` to `OrderedDict`
  - Updated `get_stats()` to include `max_limiters`

- **FastAPI Integration**
  - `LoadSheddingMiddleware.dispatch()` now returns Response objects
  - Updated all documentation examples with correct imports

### Security
- Added MIT LICENSE file for commercial use
- Clear licensing terms for reuse and distribution

### Documentation
- Created README.adoc in resilience4j style
- Added usage examples for all patterns
- Included comparison table with other libraries
- Added architecture diagram and design philosophy
- Created CHANGELOG.md following Keep a Changelog format
- Added inline code examples in docstrings
- Created installation guide

### Infrastructure
- Added `py.typed` marker for PEP 561 compliance
- Configured package for PyPI distribution
- Set up optional dependencies (redis, system, fastapi, all)
- Prepared pyproject.toml for release

## Migration Guide

### From Pre-1.0 (if you were using development versions)

#### CircuitBreaker
If you were using `can_execute()` synchronously:

```python
# Old (will not work)
if circuit.can_execute():
    result = do_something()

# New (required)
if await circuit.can_execute():
    result = await do_something()
```

#### LocalRateLimiter
The API is backward compatible, but you can now configure the cache size:

```python
# Old (still works, uses default 10000)
rate_limiter = LocalRateLimiter(service_name="api")

# New (with custom cache size)
rate_limiter = LocalRateLimiter(service_name="api", max_limiters=5000)
```

#### FastAPI Integration
Update import statements:

```python
# Old (incorrect)
from aioresilience import AsyncRateLimiter

# New (correct)
from aioresilience import RateLimiter
```

## [0.0.1] - 2025-11-04

### Added
- Initial project structure
- Basic implementations (with bugs)

---

## Versioning Policy

aioresilience follows [Semantic Versioning 2.0.0](https://semver.org/):

- **MAJOR** version for incompatible API changes
- **MINOR** version for new functionality in a backward compatible manner
- **PATCH** version for backward compatible bug fixes

## Support

For questions, issues, or feature requests, please visit:
- GitHub Issues: https://github.com/xonming/aioresilience/issues
- GitHub Discussions: https://github.com/xonming/aioresilience/discussions
