"""
Circuit Breaker Pattern Implementation

Prevents cascading failures by temporarily blocking operations that are likely to fail.
Supports async and sync operations with comprehensive metrics.
"""

import time
import asyncio
from typing import Optional, Callable, Any, TypeVar, Type, Tuple
from dataclasses import dataclass
from enum import IntEnum
from functools import wraps

from .events import EventEmitter, PatternType, EventType, CircuitBreakerEvent
from .logging import get_logger
from .config import CircuitConfig
from .exceptions import (
    CircuitBreakerOpenError,
    CircuitBreakerReason,
    ExceptionHandler,
    ExceptionContext,
    ExceptionConfig,
)

logger = get_logger(__name__)

T = TypeVar('T')


class CircuitState(IntEnum):
    """Circuit breaker states (IntEnum for performance)"""
    CLOSED = 0      # Normal operation (most common, check first)
    OPEN = 1        # Blocking requests
    HALF_OPEN = 2   # Testing recovery


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
    
    Circuit Breaker pattern for fault tolerance.
    
    Prevents cascading failures by failing fast when error thresholds are exceeded.
    Implements closed, open, and half-open states for automatic recovery.
    
    Example:
        >>> # Basic usage (all defaults)
        >>> circuit = CircuitBreaker(name="api-circuit")
        >>> 
        >>> # With custom configuration
        >>> from aioresilience import CircuitConfig, ExceptionConfig
        >>> config = CircuitConfig(failure_threshold=3, recovery_timeout=30.0)
        >>> exceptions = ExceptionConfig(exception_type=MyCustomError)
        >>> circuit = CircuitBreaker(name="api", config=config, exceptions=exceptions)
    """
    
    def __init__(
        self,
        name: str = "default",
        config: Optional[CircuitConfig] = None,
        exceptions: Optional[ExceptionConfig] = None,
    ):
        """
        Initialize circuit breaker
        
        Args:
            name: Circuit breaker name
            config: Optional CircuitConfig for pattern-specific settings
            exceptions: Optional ExceptionConfig for exception handling
        """
        # Input validation
        if not name or not name.strip():
            raise ValueError("name must be a non-empty string")
        
        self.name = name.strip()
        
        # Initialize config with defaults
        if config is None:
            config = CircuitConfig()
        
        self.failure_threshold = config.failure_threshold
        self.recovery_timeout = config.recovery_timeout
        self.success_threshold = config.success_threshold
        self.timeout = config.timeout
        self.half_open_max_calls = config.half_open_max_calls
        
        # Initialize exception handling
        if exceptions is None:
            exceptions = ExceptionConfig()
        
        # Default to Exception if not specified
        failure_exceptions = config.failure_exceptions or (Exception,)
        self.failure_exceptions = failure_exceptions
        
        self._exception_handler = ExceptionHandler(
            pattern_name=name,
            pattern_type="circuit_breaker",
            handled_exceptions=failure_exceptions,
            exception_predicate=config.failure_predicate,
            exception_type=exceptions.exception_type or CircuitBreakerOpenError,
            exception_transformer=exceptions.exception_transformer,
            on_exception=exceptions.on_exception,
        )
        
        self.state = CircuitState.CLOSED
        self.metrics = CircuitMetrics()
        self.half_open_calls = 0
        
        self._lock = asyncio.Lock()
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=name)
        
        # Performance optimization: cache whether we have event listeners
        self._has_listeners = False
        self._last_listener_check = 0.0
    
    def _check_has_listeners(self) -> bool:
        """Check if we have event listeners (cached for performance)"""
        current_time = time.time()
        # Cache for 1 second to avoid checking on every request
        if current_time - self._last_listener_check > 1.0:
            self._has_listeners = self.events.has_listeners()
            self._last_listener_check = current_time
        return self._has_listeners
    
    async def _emit_state_change(self, old_state: CircuitState, new_state: CircuitState):
        """Emit state change event (lazy - only if listeners exist)"""
        if not self._check_has_listeners():
            return  # Skip emission if no listeners
        
        await self.events.emit(CircuitBreakerEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name=self.name,
            old_state=old_state,  # Pass enum directly
            new_state=new_state,
            failure_count=self.metrics.consecutive_failures,
            success_count=self.metrics.consecutive_successes,
        ))
    
    async def _raise_circuit_open_error(self):
        """Raise exception when circuit is open using configured exception handler"""
        reason = CircuitBreakerReason.CIRCUIT_OPEN
        
        # Determine specific reason
        if self.state == CircuitState.HALF_OPEN:
            reason = CircuitBreakerReason.HALF_OPEN_REJECTION
        
        # Use exception handler to create and raise exception
        _, exc = await self._exception_handler.handle_exception(
            reason=reason,
            original_exc=None,
            message=f"Circuit breaker '{self.name}' is {self.state.name}",
            state=self.state.name.lower(),
            failure_count=self.metrics.consecutive_failures,
        )
        raise exc
    
    async def can_execute(self) -> bool:
        """
        Check if circuit breaker allows execution (async to ensure thread safety)
        
        Returns:
            True if execution allowed, False otherwise
        """
        # Always use lock for correctness - lockless check has TOCTOU race condition
        # (Reading state + consecutive_failures without lock is unsafe)
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
        # Fast path: check if state transition is needed (lock-free check)
        current_state = self.state
        needs_state_check = current_state == CircuitState.HALF_OPEN
        
        async with self._lock:
            self.metrics.total_requests += 1
            self.metrics.successful_requests += 1
            self.metrics.consecutive_successes += 1
            self.metrics.consecutive_failures = 0
            
            # Transition from HALF_OPEN to CLOSED
            if needs_state_check and self.state == CircuitState.HALF_OPEN:
                if self.metrics.consecutive_successes >= self.success_threshold:
                    old_state = self.state
                    self.state = CircuitState.CLOSED
                    self.metrics.last_state_change = time.time()
                    self.half_open_calls = 0  # Reset counter
                    logger.info(f"Circuit breaker '{self.name}': HALF_OPEN → CLOSED")
                    await self._emit_state_change(old_state, self.state)
        
        # Emit success event outside of lock (lazy)
        if self._check_has_listeners():
            await self.events.emit(CircuitBreakerEvent(
                pattern_type=PatternType.CIRCUIT_BREAKER,
                event_type=EventType.CALL_SUCCESS,
                pattern_name=self.name,
                old_state=current_state,  # Use snapshot before lock
                new_state=self.state,
                success_count=self.metrics.consecutive_successes,
            ))
    
    async def on_failure(self):
        """Handle failed execution"""
        current_state = self.state
        failure_count = 0
        
        async with self._lock:
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            self.metrics.consecutive_failures += 1
            self.metrics.consecutive_successes = 0
            self.metrics.last_failure_time = time.time()
            failure_count = self.metrics.consecutive_failures
            
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
        
        # Emit failure event outside of lock (lazy)
        if self._check_has_listeners():
            await self.events.emit(CircuitBreakerEvent(
                pattern_type=PatternType.CIRCUIT_BREAKER,
                event_type=EventType.CALL_FAILURE,
                pattern_name=self.name,
                old_state=current_state,
                new_state=self.state,
                failure_count=failure_count,
            ))
    
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
            await self._raise_circuit_open_error()
        
        # Track half-open calls (only if needed)
        if self.state == CircuitState.HALF_OPEN:
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:  # Double-check after lock
                    self.half_open_calls += 1
        
        # Cache coroutine check to avoid repeated inspect calls (5-6μs each)
        # Use id(func) as cache key for function identity
        func_id = id(func)
        if not hasattr(self, '_coro_cache'):
            self._coro_cache = {}
        
        if func_id not in self._coro_cache:
            self._coro_cache[func_id] = asyncio.iscoroutinefunction(func)
        
        is_coro = self._coro_cache[func_id]
        
        try:
            # Execute with timeout if specified
            if self.timeout:
                if is_coro:
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
                if is_coro:
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
            
            await self.on_success()
            return result
        
        except Exception as e:
            # Check if this exception should count as a failure
            if self._exception_handler.should_handle_exception(e):
                # Record the state before calling on_failure
                old_state = self.state
                
                await self.on_failure()
                logger.error(f"Circuit breaker '{self.name}': Exception {type(e).__name__}: {e}")
                
                # Call exception handler callback if configured
                if self._exception_handler.on_exception:
                    try:
                        # Determine the appropriate reason based on state transition
                        if old_state != CircuitState.OPEN and self.state == CircuitState.OPEN:
                            # Circuit just opened due to this failure
                            reason = CircuitBreakerReason.THRESHOLD_EXCEEDED
                        else:
                            # Normal failure during operation
                            reason = CircuitBreakerReason.CALL_FAILED
                        
                        context = ExceptionContext(
                            pattern_name=self.name,
                            pattern_type="circuit_breaker",
                            reason=reason,
                            original_exception=e,
                            metadata={
                                'state': self.state.name,
                                'old_state': old_state.name,
                                'failure_count': self.metrics.consecutive_failures,
                            }
                        )
                        if asyncio.iscoroutinefunction(self._exception_handler.on_exception):
                            await self._exception_handler.on_exception(context)
                        else:
                            self._exception_handler.on_exception(context)
                    except Exception as callback_error:
                        # Log callback errors but don't let them break exception handling
                        logger.error(
                            f"Circuit breaker '{self.name}': Error in on_exception callback: "
                            f"{type(callback_error).__name__}: {callback_error}"
                        )
            else:
                # Exception doesn't count as failure, but still log it
                logger.debug(f"Circuit breaker '{self.name}': Non-failure exception {type(e).__name__}: {e}")
            raise
        
        finally:
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.half_open_calls = max(0, self.half_open_calls - 1)
    
    
    def get_state(self) -> CircuitState:
        """Get current state"""
        return self.state
    
    def get_metrics(self) -> dict:
        """Get circuit breaker metrics"""
        return {
            "name": self.name,
            "state": self.state.name.lower(),  # Use .name for display (e.g., "closed")
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
                old_state=old_state,  # Pass enum directly
                new_state=self.state,
            ))


# Decorator for circuit breaker
def circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: float = 60.0,
    **kwargs
):
    """
    Decorator to add circuit breaker to a function (convenience pattern).
    
    Creates a new CircuitBreaker instance. For reusable instances across
    multiple functions, use @with_circuit_breaker(circuit) instead.
    
    Example:
        @circuit_breaker("external_api", failure_threshold=3, recovery_timeout=30)
        async def call_external_api():
            return await httpx.get("https://api.example.com")
    
    Recommended (instance-based):
        circuit = CircuitBreaker(name="api", config=CircuitConfig(failure_threshold=3))
        
        @with_circuit_breaker(circuit)
        async def call_external_api():
            return await httpx.get("https://api.example.com")
    """
    # Build config from parameters for backward compatibility
    config = CircuitConfig(
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        **{k: v for k, v in kwargs.items() if k in ['success_threshold', 'timeout', 'half_open_max_calls', 'failure_exceptions', 'failure_predicate']}
    )
    # Extract exception config parameters if provided
    exception_kwargs = {k: v for k, v in kwargs.items() if k in ['exception_type', 'exception_transformer', 'on_exception', 'handled_exceptions', 'exception_predicate']}
    exceptions = ExceptionConfig(**exception_kwargs) if exception_kwargs else None
    
    cb = CircuitBreaker(name=name, config=config, exceptions=exceptions)
    
    def decorator(func: Callable) -> Callable:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError(
                f"Circuit breaker decorator can only be applied to async functions. "
                f"'{func.__name__}' is not async. Use 'async def' or call circuit_breaker.call() manually."
            )
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await cb.call(func, *args, **kwargs)
        
        async_wrapper.circuit_breaker = cb  # Expose circuit breaker instance
        return async_wrapper
    
    return decorator


def with_circuit_breaker(circuit: CircuitBreaker):
    """
    Decorator to use an existing CircuitBreaker instance.
    
    Args:
        circuit: Existing CircuitBreaker instance to use
        
    Example:
        circuit = CircuitBreaker(name="api", config=CircuitConfig(failure_threshold=5))
        
        @with_circuit_breaker(circuit)
        async def call_external_api():
            return await httpx.get("https://api.example.com")
    """
    def decorator(func: Callable) -> Callable:
        if not asyncio.iscoroutinefunction(func):
            raise TypeError(
                f"Circuit breaker decorator can only be applied to async functions. "
                f"'{func.__name__}' is not async. Use 'async def' or call circuit_breaker.call() manually."
            )
        
        @wraps(func)
        async def async_wrapper(*args, **kwargs) -> Any:
            return await circuit.call(func, *args, **kwargs)
        
        async_wrapper.circuit_breaker = circuit  # Expose circuit breaker instance
        return async_wrapper
    
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
            # Build config from kwargs for backward compatibility
            config_params = {k: v for k, v in kwargs.items() if k in ['failure_threshold', 'recovery_timeout', 'success_threshold', 'timeout', 'half_open_max_calls', 'failure_exceptions', 'failure_predicate']}
            exception_params = {k: v for k, v in kwargs.items() if k in ['exception_type', 'exception_transformer', 'on_exception', 'handled_exceptions', 'exception_predicate']}
            
            config = CircuitConfig(**config_params) if config_params else None
            exceptions = ExceptionConfig(**exception_params) if exception_params else None
            
            self.breakers[name] = CircuitBreaker(name=name, config=config, exceptions=exceptions)
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
