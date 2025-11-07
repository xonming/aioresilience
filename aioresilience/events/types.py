"""
Event types and classes for resilience patterns
"""

from enum import IntEnum
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, TYPE_CHECKING
import time

if TYPE_CHECKING:
    from ..circuit_breaker import CircuitState


class PatternType(IntEnum):
    """Resilience pattern types (IntEnum for performance)"""
    CIRCUIT_BREAKER = 0
    BULKHEAD = 1
    TIMEOUT = 2
    RETRY = 3
    RATE_LIMITER = 4
    LOAD_SHEDDER = 5
    BACKPRESSURE = 6
    FALLBACK = 7
    ADAPTIVE_CONCURRENCY = 8


class EventType(IntEnum):
    """Event types for resilience patterns (IntEnum for performance)"""
    # Common events
    INITIALIZED = 0
    
    # Circuit Breaker events (1-10)
    STATE_CHANGE = 1
    CALL_SUCCESS = 2
    CALL_FAILURE = 3
    CIRCUIT_RESET = 4
    HALF_OPEN_PROBE = 5
    
    # Bulkhead events (11-20)
    SLOT_ACQUIRED = 11
    SLOT_RELEASED = 12
    BULKHEAD_FULL = 13
    QUEUE_FULL = 14
    
    # Timeout events (21-30)
    TIMEOUT_OCCURRED = 21
    TIMEOUT_SUCCESS = 22
    
    # Retry events (31-40)
    RETRY_ATTEMPT = 31
    RETRY_EXHAUSTED = 32
    RETRY_SUCCESS = 33
    
    # Rate Limiter events (41-50)
    REQUEST_ALLOWED = 41
    REQUEST_REJECTED = 42
    LIMIT_UPDATED = 43
    WINDOW_RESET = 44
    
    # Load Shedder events (51-60)
    REQUEST_SHED = 51
    REQUEST_ACCEPTED = 52
    LOAD_LEVEL_CHANGE = 53
    THRESHOLD_EXCEEDED = 54
    
    # Fallback events (61-70)
    FALLBACK_EXECUTED = 61
    PRIMARY_FAILED = 62


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
            "pattern_type": self.pattern_type.name.lower(),
            "event_type": self.event_type.name.lower(),
            "pattern_name": self.pattern_name,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class CircuitBreakerEvent(ResilienceEvent):
    """Circuit breaker specific event"""
    old_state: Optional[Any] = None  # CircuitState enum
    new_state: Optional[Any] = None  # CircuitState enum
    failure_count: int = 0
    success_count: int = 0
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            "old_state": self.old_state.name.lower() if hasattr(self.old_state, 'name') else self.old_state,
            "new_state": self.new_state.name.lower() if hasattr(self.new_state, 'name') else self.new_state,
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
