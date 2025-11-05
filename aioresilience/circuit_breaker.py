"""
Circuit Breaker Pattern Implementation

Prevents cascading failures by temporarily blocking operations that are likely to fail.
Supports async and sync operations with comprehensive metrics.
"""

import time
import asyncio
from typing import Optional, Callable, Any, TypeVar
from dataclasses import dataclass
from enum import Enum
from functools import wraps
import logging

from .events import EventEmitter, PatternType, EventType, CircuitBreakerEvent

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitMetrics:
    """Circuit breaker metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[float] = None
    last_state_change: float = 0.0
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate"""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        return 1.0 - self.failure_rate


class CircuitBreaker:
    """
    Circuit breaker implementation with async and sync support
    
    States:
    - CLOSED: Normal operation
    - OPEN: Failing fast (blocking all requests)
    - HALF_OPEN: Testing recovery
    
    Example (manual):
        from aioresilience import CircuitBreaker
        
        breaker = CircuitBreaker(
            name="redis",
            failure_threshold=3,
            recovery_timeout=30
        )
        
        if breaker.can_execute():
            try:
                result = await do_something()
                breaker.on_success()
            except Exception:
                breaker.on_failure()
                raise
    
    Example (decorator):
        from aioresilience import circuit_breaker
        
        @circuit_breaker("external_api", failure_threshold=5)
        async def call_api():
            return await httpx.get("https://api.example.com")
    """
    
    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: type = Exception,
        success_threshold: int = 2,
        timeout: Optional[float] = None,
        half_open_max_calls: int = 1,
    ):
        """
        Initialize circuit breaker
        
        Args:
            name: Circuit breaker name
            failure_threshold: Consecutive failures to open circuit
            recovery_timeout: Seconds before trying to recover
            expected_exception: Exception type to catch
            success_threshold: Successes in half-open to close
            timeout: Operation timeout in seconds
            half_open_max_calls: Max concurrent calls in half-open
        """
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.metrics = CircuitMetrics()
        self.half_open_calls = 0
        
        self._lock = asyncio.Lock()
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=name)
    
    async def _emit_state_change(self, old_state: CircuitState, new_state: CircuitState):
        """Emit state change event"""
        await self.events.emit(CircuitBreakerEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name=self.name,
            old_state=old_state.value,
            new_state=new_state.value,
            failure_count=self.metrics.consecutive_failures,
            success_count=self.metrics.consecutive_successes,
        ))
    
    async def can_execute(self) -> bool:
        """
        Check if circuit breaker allows execution (async to ensure thread safety)
        
        Returns:
            True if execution allowed, False otherwise
        """
        async with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            elif self.state == CircuitState.OPEN:
                if self.metrics.last_failure_time and time.time() - self.metrics.last_failure_time > self.recovery_timeout:
                    # Transition to half-open
                    old_state = self.state
                    self.state = CircuitState.HALF_OPEN
                    self.metrics.last_state_change = time.time()
                    self.half_open_calls = 0  # Reset counter
                    logger.info(f"Circuit breaker '{self.name}': OPEN → HALF_OPEN")
                    await self._emit_state_change(old_state, self.state)
                    return True
                return False
            else:  # HALF_OPEN
                return self.half_open_calls < self.half_open_max_calls
    
    async def on_success(self):
        """Handle successful execution"""
        async with self._lock:
            self.metrics.total_requests += 1
            self.metrics.successful_requests += 1
            self.metrics.consecutive_successes += 1
            self.metrics.consecutive_failures = 0
            
            # Emit success event
            await self.events.emit(CircuitBreakerEvent(
                pattern_type=PatternType.CIRCUIT_BREAKER,
                event_type=EventType.CALL_SUCCESS,
                pattern_name=self.name,
                old_state=self.state.value,
                new_state=self.state.value,
                success_count=self.metrics.consecutive_successes,
            ))
            
            # Transition from HALF_OPEN to CLOSED
            if self.state == CircuitState.HALF_OPEN:
                if self.metrics.consecutive_successes >= self.success_threshold:
                    old_state = self.state
                    self.state = CircuitState.CLOSED
                    self.metrics.last_state_change = time.time()
                    self.half_open_calls = 0  # Reset counter
                    logger.info(f"Circuit breaker '{self.name}': HALF_OPEN → CLOSED")
                    await self._emit_state_change(old_state, self.state)
    
    async def on_failure(self):
        """Handle failed execution"""
        async with self._lock:
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.consecutive_failures += 1
            self.metrics.consecutive_successes = 0
            self.metrics.last_failure_time = time.time()
            
            # Emit failure event
            await self.events.emit(CircuitBreakerEvent(
                pattern_type=PatternType.CIRCUIT_BREAKER,
                event_type=EventType.CALL_FAILURE,
                pattern_name=self.name,
                old_state=self.state.value,
                new_state=self.state.value,
                failure_count=self.metrics.consecutive_failures,
            ))
            
            # Transition to OPEN if threshold exceeded
            if self.state == CircuitState.CLOSED:
                if self.metrics.consecutive_failures >= self.failure_threshold:
                    old_state = self.state
                    self.state = CircuitState.OPEN
                    self.metrics.last_state_change = time.time()
                    logger.error(
                        f"Circuit breaker '{self.name}': CLOSED → OPEN "
                        f"(failures: {self.metrics.consecutive_failures})"
                    )
                    await self._emit_state_change(old_state, self.state)
            
            # Transition back to OPEN from HALF_OPEN
            elif self.state == CircuitState.HALF_OPEN:
                old_state = self.state
                self.state = CircuitState.OPEN
                self.metrics.last_state_change = time.time()
                self.half_open_calls = 0  # Reset counter
                logger.warning(f"Circuit breaker '{self.name}': HALF_OPEN → OPEN")
                await self._emit_state_change(old_state, self.state)
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function through circuit breaker (async)
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        
        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: If function fails
        """
        # Check if circuit is open
        if not await self.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is {self.state.value.upper()}"
            )
        
        # Track half-open calls
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_calls += 1
        
        try:
            # Execute with timeout if specified
            if self.timeout:
                if asyncio.iscoroutinefunction(func):
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=self.timeout
                    )
                else:
                    result = await asyncio.wait_for(
                        asyncio.to_thread(func, *args, **kwargs),
                        timeout=self.timeout
                    )
            else:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
            
            await self.on_success()
            return result
        
        except asyncio.TimeoutError as e:
            await self.on_failure()
            logger.error(f"Circuit breaker '{self.name}': Timeout after {self.timeout}s")
            raise
        
        except self.expected_exception as e:
            await self.on_failure()
            raise
        
        finally:
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.half_open_calls = max(0, self.half_open_calls - 1)
    
    def call_sync(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute function through circuit breaker (sync)
        
        Note: This is provided for backward compatibility but is not thread-safe.
        For production use, prefer the async call() method.
        """
        # Create event loop if needed for lock operations
        import warnings
        warnings.warn(
            "call_sync is not thread-safe. Use async call() method for production.",
            RuntimeWarning,
            stacklevel=2
        )
        
        # Simple sync check without lock (not thread-safe)
        if self.state == CircuitState.CLOSED:
            can_exec = True
        elif self.state == CircuitState.OPEN:
            if self.metrics.last_failure_time and time.time() - self.metrics.last_failure_time > self.recovery_timeout:
                can_exec = True
            else:
                can_exec = False
        else:  # HALF_OPEN
            can_exec = self.half_open_calls < self.half_open_max_calls
        
        if not can_exec:
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is {self.state.value.upper()}"
            )
        
        try:
            result = func(*args, **kwargs)
            # Note: Not calling on_success in sync mode to avoid lock issues
            self.metrics.total_requests += 1
            self.metrics.successful_requests += 1
            return result
        except self.expected_exception as e:
            # Note: Not calling on_failure in sync mode to avoid lock issues
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            raise
    
    def get_state(self) -> CircuitState:
        """Get current state"""
        return self.state
    
    def get_metrics(self) -> dict:
        """Get circuit breaker metrics"""
        return {
            "name": self.name,
            "state": self.state.value,
            "total_requests": self.metrics.total_requests,
            "successful_requests": self.metrics.successful_requests,
            "failed_requests": self.metrics.failed_requests,
            "failure_rate": self.metrics.failure_rate,
            "consecutive_failures": self.metrics.consecutive_failures,
            "consecutive_successes": self.metrics.consecutive_successes,
            "last_failure_time": self.metrics.last_failure_time,
            "time_since_last_failure": (
                time.time() - self.metrics.last_failure_time 
                if self.metrics.last_failure_time else None
            ),
        }
    
    async def reset(self):
        """Manually reset circuit breaker"""
        async with self._lock:
            old_state = self.state
            self.state = CircuitState.CLOSED
            self.metrics = CircuitMetrics()
            self.half_open_calls = 0
            logger.info(f"Circuit breaker '{self.name}': Manually reset")
            
            # Emit reset event
            await self.events.emit(CircuitBreakerEvent(
                pattern_type=PatternType.CIRCUIT_BREAKER,
                event_type=EventType.CIRCUIT_RESET,
                pattern_name=self.name,
                old_state=old_state.value,
                new_state=self.state.value,
            ))


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass


# Decorator for circuit breaker
def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    **kwargs
):
    """
    Decorator to add circuit breaker to a function
    
    Example:
        @circuit_breaker("external_api", failure_threshold=3, recovery_timeout=30)
        async def call_external_api():
            return await httpx.get("https://api.example.com")
    """
    cb = CircuitBreaker(name, failure_threshold, recovery_timeout, **kwargs)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await cb.call(func, *args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs) -> Any:
            return cb.call_sync(func, *args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            wrapper = async_wrapper
        else:
            wrapper = sync_wrapper
        
        wrapper.circuit_breaker = cb  # Expose circuit breaker instance
        return wrapper
    
    return decorator


class CircuitBreakerManager:
    """Manager for multiple circuit breakers"""
    
    def __init__(self):
        self.breakers: dict[str, CircuitBreaker] = {}
    
    def get_or_create(
        self,
        name: str,
        **kwargs
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker"""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(name, **kwargs)
        return self.breakers[name]
    
    def get_all_metrics(self) -> dict:
        """Get metrics for all circuit breakers"""
        return {
            name: breaker.get_metrics()
            for name, breaker in self.breakers.items()
        }
    
    def get_open_circuits(self) -> list[str]:
        """Get list of open circuit breakers"""
        return [
            name for name, breaker in self.breakers.items()
            if breaker.get_state() == CircuitState.OPEN
        ]
    
    async def reset_all(self):
        """Reset all circuit breakers"""
        for breaker in self.breakers.values():
            await breaker.reset()


# Global circuit breaker manager
_circuit_manager = CircuitBreakerManager()


def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """
    Get or create a circuit breaker from global manager
    
    Example:
        from aioresilience import get_circuit_breaker
        
        redis_breaker = get_circuit_breaker(
            "redis",
            failure_threshold=3,
            recovery_timeout=30
        )
    """
    return _circuit_manager.get_or_create(name, **kwargs)


def get_all_circuit_metrics() -> dict:
    """Get metrics for all circuit breakers"""
    return _circuit_manager.get_all_metrics()
