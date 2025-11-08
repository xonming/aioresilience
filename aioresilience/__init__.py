"""
aioresilience - Async Resilience Patterns for Python

Modular, dependency-optional toolkit for building resilient distributed systems.

Core Features (No Optional Dependencies):
- Circuit Breakers - Prevent cascading failures
- Retry - Exponential backoff with jitter
- Timeout/Deadline - Time-bound operations
- Bulkhead - Resource isolation
- Fallback - Graceful degradation
- Backpressure - Control flow in async pipelines  
- Adaptive Concurrency - Auto-adjust based on success rate
- Basic Load Shedding - Request count limits
- Local Rate Limiting - In-memory rate limiting
- Event System - Local and global event handlers for observability
- Flexible Logging - Silent by default, supports any logging framework

Optional Features (Require Installation):
- System Load Shedding - CPU/memory monitoring (requires psutil)
- Distributed Rate Limiting - Redis-backed (requires redis)
- Framework Integrations - FastAPI, aiohttp, Sanic

Usage:
    # Core (always available)
    from aioresilience import (
        CircuitBreaker, RetryPolicy, Bulkhead, 
        FallbackHandler, TimeoutManager
    )
    
    # Default implementations
    from aioresilience import RateLimiter, LoadShedder
    
    # Event system
    from aioresilience import global_bus, EventType
    
    # Logging configuration
    from aioresilience import configure_logging, set_error_handler
    
    # Explicit implementations
    from aioresilience.rate_limiting import LocalRateLimiter, RedisRateLimiter
    from aioresilience.load_shedding import BasicLoadShedder, SystemLoadShedder
"""

# Core modules (no optional dependencies)

# Configuration classes
from .config import (
    CircuitConfig,
    BulkheadConfig,
    TimeoutConfig,
    BackpressureConfig,
    LoadSheddingConfig,
    RetryConfig,
    RateLimitConfig,
    FallbackConfig,
    AdaptiveConcurrencyConfig,
)

# Exception System
from .exceptions import (
    # Base classes
    ResilienceError,
    ExceptionContext,
    ExceptionAction,
    # Configuration
    ExceptionConfig,
    create_exception_config,
    # Reason enums
    CircuitBreakerReason,
    BulkheadReason,
    TimeoutReason,
    RetryReason,
    BackpressureReason,
    LoadSheddingReason,
    RateLimitReason,
    FallbackReason,
    # Exception types
    CircuitBreakerOpenError,
    BulkheadFullError,
    OperationTimeoutError,
    BackpressureError,
    LoadSheddingError,
    RateLimitExceededError,
    FallbackFailedError,
    # Handler
    ExceptionHandler,
)

from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    circuit_breaker,
    with_circuit_breaker,
    CircuitBreakerManager,
    get_circuit_breaker,
    get_all_circuit_metrics,
)

from .backpressure import (
    BackpressureManager,
    with_backpressure,
)

from .adaptive_concurrency import (
    AdaptiveConcurrencyLimiter,
)

from .retry import (
    RetryPolicy,
    RetryStrategy,
    retry,
    with_retry,
    RetryPolicies,
)

from .timeout import (
    TimeoutManager,
    DeadlineManager,
    timeout,
    with_timeout_manager,
    with_timeout,
    with_deadline,
)

from .bulkhead import (
    Bulkhead,
    bulkhead,
    with_bulkhead,
    get_bulkhead,
    get_all_bulkhead_metrics,
)

from .fallback import (
    FallbackHandler,
    ChainedFallback,
    fallback,
    chained_fallback,
    with_fallback_handler,
    with_fallback,
)

# Modular imports with defaults
from .rate_limiting import (
    RateLimiter,  # Alias for LocalRateLimiter
    LocalRateLimiter,
)

from .load_shedding import (
    LoadShedder,  # Alias for BasicLoadShedder
    BasicLoadShedder,
    LoadLevel,
    LoadMetrics,
    with_load_shedding,
)

# Event System
from .events import (
    EventEmitter,
    global_bus,
    PatternType,
    EventType,
    ResilienceEvent,
    CircuitBreakerEvent,
    RateLimitEvent,
    BulkheadEvent,
    LoadShedderEvent,
    RetryEvent,
    TimeoutEvent,
    FallbackEvent,
)

# Logging Configuration
from .logging import (
    configure_logging,
    set_error_handler,
    disable_logging,
    is_logging_enabled,
)

__all__ = [
    # Configuration Classes
    "CircuitConfig",
    "BulkheadConfig",
    "TimeoutConfig",
    "BackpressureConfig",
    "LoadSheddingConfig",
    "RetryConfig",
    "RateLimitConfig",
    "FallbackConfig",
    "AdaptiveConcurrencyConfig",
    
    # Exception System
    "ResilienceError",
    "ExceptionContext",
    "ExceptionAction",
    "ExceptionConfig",
    "create_exception_config",
    "CircuitBreakerReason",
    "BulkheadReason",
    "TimeoutReason",
    "RetryReason",
    "BackpressureReason",
    "LoadSheddingReason",
    "RateLimitReason",
    "FallbackReason",
    "CircuitBreakerOpenError",
    "BulkheadFullError",
    "OperationTimeoutError",
    "BackpressureError",
    "LoadSheddingError",
    "RateLimitExceededError",
    "FallbackFailedError",
    "ExceptionHandler",
    
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitState",
    "circuit_breaker",
    "with_circuit_breaker",
    "CircuitBreakerManager",
    "get_circuit_breaker",
    "get_all_circuit_metrics",
    
    # Retry
    "RetryPolicy",
    "RetryStrategy",
    "retry",
    "with_retry",
    "RetryPolicies",
    
    # Timeout & Deadline
    "TimeoutManager",
    "DeadlineManager",
    "timeout",
    "with_timeout_manager",
    "with_timeout",
    "with_deadline",
    
    # Bulkhead
    "Bulkhead",
    "bulkhead",
    "with_bulkhead",
    "get_bulkhead",
    "get_all_bulkhead_metrics",
    
    # Fallback
    "FallbackHandler",
    "ChainedFallback",
    "fallback",
    "chained_fallback",
    "with_fallback_handler",
    "with_fallback",
    
    # Backpressure
    "BackpressureManager",
    "with_backpressure",
    
    # Adaptive Concurrency
    "AdaptiveConcurrencyLimiter",
    
    # Rate Limiting
    "RateLimiter",  # Default: LocalRateLimiter
    "LocalRateLimiter",
    
    # Load Shedding
    "LoadShedder",  # Default: BasicLoadShedder
    "BasicLoadShedder",
    "LoadLevel",
    "LoadMetrics",
    "with_load_shedding",
    
    # Event System
    "EventEmitter",
    "global_bus",
    "PatternType",
    "EventType",
    "ResilienceEvent",
    "CircuitBreakerEvent",
    "RateLimitEvent",
    "BulkheadEvent",
    "LoadShedderEvent",
    "RetryEvent",
    "TimeoutEvent",
    "FallbackEvent",
    
    # Logging Configuration
    "configure_logging",
    "set_error_handler",
    "disable_logging",
    "is_logging_enabled",
]

__version__ = "0.2.1"
__author__ = "xonming"
__license__ = "MIT"
