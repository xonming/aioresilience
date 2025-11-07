"""
Specific exception types for each resilience pattern.

All inherit from ResilienceError to provide rich context.
"""

from .base import ResilienceError


class CircuitBreakerOpenError(ResilienceError):
    """
    Raised when circuit breaker is open and blocks a request.
    
    The circuit breaker has detected too many failures and is preventing
    requests from reaching the failing service.
    """
    pass


class BulkheadFullError(ResilienceError):
    """
    Raised when bulkhead is at capacity and cannot accept more requests.
    
    All concurrent execution slots are occupied and the waiting queue
    is full or the request timed out waiting.
    """
    pass


class OperationTimeoutError(ResilienceError):
    """
    Raised when an operation exceeds its timeout or deadline.
    
    The operation took longer than the configured timeout period
    or exceeded an absolute deadline.
    """
    pass


class BackpressureError(ResilienceError):
    """
    Raised when backpressure mechanism rejects a request.
    
    The system is overloaded and cannot accept additional work
    at this time to maintain stability.
    """
    pass


class LoadSheddingError(ResilienceError):
    """Raised when load shedding rejects a request"""
    pass


class RateLimitExceededError(ResilienceError):
    """Raised when rate limit is exceeded"""
    pass


class FallbackFailedError(ResilienceError):
    """Raised when all fallback attempts fail"""
    pass
