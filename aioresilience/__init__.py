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

Optional Features (Require Installation):
- System Load Shedding - CPU/memory monitoring (requires psutil)
- Distributed Rate Limiting - Redis-backed (requires redis)
- Framework Integrations - FastAPI, Flask, etc.

Usage:
    # Core (always available)
    from aioresilience import (
        CircuitBreaker, RetryPolicy, Bulkhead, 
        FallbackHandler, TimeoutManager
    )
    
    # Default implementations
    from aioresilience import RateLimiter, LoadShedder
    
    # Explicit implementations
    from aioresilience.rate_limiting import LocalRateLimiter, RedisRateLimiter
    from aioresilience.load_shedding import BasicLoadShedder, SystemLoadShedder
"""

# Core modules (no optional dependencies)
from .circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    circuit_breaker,
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
    RetryPolicies,
)

from .timeout import (
    TimeoutManager,
    DeadlineManager,
    timeout,
    with_timeout,
    with_deadline,
    TimeoutError,
)

from .bulkhead import (
    Bulkhead,
    BulkheadFullError,
    bulkhead,
    get_bulkhead,
    get_all_bulkhead_metrics,
)

from .fallback import (
    FallbackHandler,
    ChainedFallback,
    fallback,
    chained_fallback,
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

__all__ = [
    # Circuit Breaker
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerOpenError",
    "circuit_breaker",
    "CircuitBreakerManager",
    "get_circuit_breaker",
    "get_all_circuit_metrics",
    
    # Retry
    "RetryPolicy",
    "RetryStrategy",
    "retry",
    "RetryPolicies",
    
    # Timeout & Deadline
    "TimeoutManager",
    "DeadlineManager",
    "timeout",
    "with_timeout",
    "with_deadline",
    "TimeoutError",
    
    # Bulkhead
    "Bulkhead",
    "BulkheadFullError",
    "bulkhead",
    "get_bulkhead",
    "get_all_bulkhead_metrics",
    
    # Fallback
    "FallbackHandler",
    "ChainedFallback",
    "fallback",
    "chained_fallback",
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
]

__version__ = "0.1.0"
__author__ = "xonming"
__license__ = "MIT"
