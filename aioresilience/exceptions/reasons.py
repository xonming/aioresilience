"""
Reason codes for exception handling across patterns.

Each pattern has its own IntEnum defining why an exception was raised.
Using IntEnum for fast integer comparisons in hot paths.
"""

from enum import IntEnum


class CircuitBreakerReason(IntEnum):
    """Reasons why circuit breaker raises an exception"""
    CIRCUIT_OPEN = 0           # Circuit is in OPEN state (most common)
    TIMEOUT = 1                # Operation timed out
    HALF_OPEN_REJECTION = 2    # Half-open state rejecting calls
    CALL_FAILED = 3            # Call failed during normal operation (for callbacks)
    THRESHOLD_EXCEEDED = 4     # Failure threshold exceeded, circuit opening


class BulkheadReason(IntEnum):
    """Reasons why bulkhead raises an exception"""
    CAPACITY_FULL = 0          # Max concurrent slots occupied (most common)
    QUEUE_FULL = 1             # Waiting queue is full
    TIMEOUT = 2                # Timeout while waiting for slot


class TimeoutReason(IntEnum):
    """Reasons why timeout raises an exception"""
    TIMEOUT_EXCEEDED = 0       # Operation exceeded timeout (most common)
    DEADLINE_EXCEEDED = 1      # Operation exceeded absolute deadline


class RetryReason(IntEnum):
    """Reasons why retry raises an exception"""
    EXHAUSTED = 0              # All retry attempts failed (most common)
    NON_RETRYABLE = 1          # Exception is not retryable


class BackpressureReason(IntEnum):
    """Reasons why backpressure raises an exception"""
    SYSTEM_OVERLOADED = 0      # System is overloaded (most common)
    TIMEOUT_ACQUIRING = 1      # Timeout while waiting to acquire


class LoadSheddingReason(IntEnum):
    """Reasons why load shedding raises an exception"""
    MAX_LOAD_EXCEEDED = 0      # Maximum load threshold exceeded (most common)
    PRIORITY_REJECTED = 1      # Request priority too low


class RateLimitReason(IntEnum):
    """Reasons why rate limiter raises an exception"""
    RATE_LIMIT_EXCEEDED = 0    # Rate limit exceeded (most common)
    QUOTA_EXCEEDED = 1         # Quota exceeded
    WINDOW_EXHAUSTED = 2       # Time window exhausted


class FallbackReason(IntEnum):
    """Reasons why fallback raises an exception"""
    ALL_FALLBACKS_FAILED = 0   # All fallback attempts failed (most common)
    FALLBACK_ERROR = 1         # Fallback execution error
    NO_FALLBACK_DEFINED = 2    # No fallback was defined
