"""
Event types and classes for resilience patterns
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any, Dict
import time


class PatternType(Enum):
    """Resilience pattern types"""
    CIRCUIT_BREAKER = "circuit_breaker"
    RATE_LIMITER = "rate_limiter"
    BULKHEAD = "bulkhead"
    LOAD_SHEDDER = "load_shedder"
    RETRY = "retry"
    TIMEOUT = "timeout"
    FALLBACK = "fallback"
    BACKPRESSURE = "backpressure"
    ADAPTIVE_CONCURRENCY = "adaptive_concurrency"


class EventType(Enum):
    """Event types for resilience patterns"""
    # Common events
    INITIALIZED = "initialized"
    
    # Circuit Breaker events
    STATE_CHANGE = "state_change"
    CALL_SUCCESS = "call_success"
    CALL_FAILURE = "call_failure"
    CIRCUIT_RESET = "circuit_reset"
    HALF_OPEN_PROBE = "half_open_probe"
    
    # Rate Limiter events
    REQUEST_ALLOWED = "request_allowed"
    REQUEST_REJECTED = "request_rejected"
    LIMIT_UPDATED = "limit_updated"
    WINDOW_RESET = "window_reset"
    
    # Bulkhead events
    SLOT_ACQUIRED = "slot_acquired"
    SLOT_RELEASED = "slot_released"
    BULKHEAD_FULL = "bulkhead_full"
    QUEUE_FULL = "queue_full"
    
    # Load Shedder events
    REQUEST_SHED = "request_shed"
    REQUEST_ACCEPTED = "request_accepted"
    LOAD_LEVEL_CHANGE = "load_level_change"
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    
    # Retry events
    RETRY_ATTEMPT = "retry_attempt"
    RETRY_EXHAUSTED = "retry_exhausted"
    RETRY_SUCCESS = "retry_success"
    
    # Timeout events
    TIMEOUT_OCCURRED = "timeout_occurred"
    TIMEOUT_SUCCESS = "timeout_success"
    
    # Fallback events
    FALLBACK_EXECUTED = "fallback_executed"
    PRIMARY_FAILED = "primary_failed"


@dataclass
class ResilienceEvent:
    """Base event for all resilience patterns"""
    pattern_type: PatternType
    event_type: EventType
    pattern_name: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert event to dictionary"""
        return {
            "pattern_type": self.pattern_type.value,
            "event_type": self.event_type.value,
            "pattern_name": self.pattern_name,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class CircuitBreakerEvent(ResilienceEvent):
    """Circuit breaker specific event"""
    old_state: Optional[str] = None
    new_state: Optional[str] = None
    failure_count: int = 0
    success_count: int = 0
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "old_state": self.old_state,
            "new_state": self.new_state,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
        })
        return base


@dataclass
class RateLimitEvent(ResilienceEvent):
    """Rate limiter specific event"""
    user_id: Optional[str] = None
    limit: Optional[str] = None
    current_count: int = 0
    remaining: int = 0
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "user_id": self.user_id,
            "limit": self.limit,
            "current_count": self.current_count,
            "remaining": self.remaining,
        })
        return base


@dataclass
class BulkheadEvent(ResilienceEvent):
    """Bulkhead specific event"""
    active_count: int = 0
    waiting_count: int = 0
    max_concurrent: int = 0
    max_waiting: int = 0
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "active_count": self.active_count,
            "waiting_count": self.waiting_count,
            "max_concurrent": self.max_concurrent,
            "max_waiting": self.max_waiting,
        })
        return base


@dataclass
class LoadShedderEvent(ResilienceEvent):
    """Load shedder specific event"""
    active_requests: int = 0
    max_requests: int = 0
    load_level: float = 0.0
    reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "active_requests": self.active_requests,
            "max_requests": self.max_requests,
            "load_level": self.load_level,
            "reason": self.reason,
        })
        return base


@dataclass
class RetryEvent(ResilienceEvent):
    """Retry specific event"""
    attempt: int = 0
    max_attempts: int = 0
    delay: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "delay": self.delay,
            "error": self.error,
        })
        return base


@dataclass
class TimeoutEvent(ResilienceEvent):
    """Timeout specific event"""
    timeout_value: float = 0.0
    elapsed: float = 0.0
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "timeout_value": self.timeout_value,
            "elapsed": self.elapsed,
        })
        return base


@dataclass
class FallbackEvent(ResilienceEvent):
    """Fallback specific event"""
    primary_error: Optional[str] = None
    fallback_value: Optional[Any] = None
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "primary_error": self.primary_error,
            "fallback_value": str(self.fallback_value) if self.fallback_value else None,
        })
        return base
