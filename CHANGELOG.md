# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned Features
- Retry policies with exponential backoff
- Bulkhead pattern for resource isolation
- Time limiters / deadlines
- Enhanced fallback mechanisms
- Django integration
- Flask integration
- Prometheus metrics exporter
- OpenTelemetry integration

## [0.1.0] - 2025-11-05

### Added

#### Core Features
- **Circuit Breaker Pattern**
  - Async-first implementation with CLOSED, OPEN, and HALF_OPEN states
  - Automatic failure detection and recovery
  - Configurable failure threshold, recovery timeout, and success threshold
  - Rich metrics tracking (total requests, failures, success rate, consecutive failures)
  - Global circuit breaker manager for centralized management
  - Decorator support (`@circuit_breaker`) for easy integration
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
  - Comprehensive docstrings with examples
  - Decorator patterns for all major features
  - Rich error messages and structured logging
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
  - Automatic cleanup of least recently used limiters
  - Added lock protection for limiter dictionary access
  - Prevents unbounded memory growth with many unique keys

- **FastAPI Integration**
  - Fixed middleware to return JSONResponse instead of raising HTTPException
  - Updated `rate_limit_dependency` documentation with correct class names
  - Changed from `AsyncRateLimiter` (non-existent) to `RateLimiter`
  - Added proper HTTP status code constants (HTTP_429_TOO_MANY_REQUESTS)
  - Improved error response format

### Changed

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
- Created comprehensive README.adoc in resilience4j style
- Added detailed usage examples for all patterns
- Included comparison table with other libraries
- Added architecture diagram and design philosophy
- Created CHANGELOG.md following Keep a Changelog format
- Added inline code examples in docstrings
- Created comprehensive installation guide

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
