"""
Exception handling system for aioresilience.

Provides:
- Base exception classes with rich context
- Exception handling strategies
- Reason enums for each pattern
- Exception transformers and context
"""

from .base import (
    ResilienceError,
    ExceptionContext,
    ExceptionAction,
)
from .reasons import (
    CircuitBreakerReason,
    BulkheadReason,
    TimeoutReason,
    RetryReason,
    BackpressureReason,
    LoadSheddingReason,
    RateLimitReason,
    FallbackReason,
)
from .errors import (
    CircuitBreakerOpenError,
    BulkheadFullError,
    OperationTimeoutError,
    BackpressureError,
    LoadSheddingError,
    RateLimitExceededError,
    FallbackFailedError,
)
from .handler import ExceptionHandler
from .config import ExceptionConfig, create_exception_config

__all__ = [
    # Base classes
    "ResilienceError",
    "ExceptionContext",
    "ExceptionAction",
    
    # Configuration
    "ExceptionConfig",
    "create_exception_config",
    
    # Reason enums
    "CircuitBreakerReason",
    "BulkheadReason",
    "TimeoutReason",
    "RetryReason",
    "BackpressureReason",
    "LoadSheddingReason",
    "RateLimitReason",
    "FallbackReason",
    
    # Exception types
    "CircuitBreakerOpenError",
    "BulkheadFullError",
    "OperationTimeoutError",
    "BackpressureError",
    "LoadSheddingError",
    "RateLimitExceededError",
    "FallbackFailedError",
    
    # Handler
    "ExceptionHandler",
]
