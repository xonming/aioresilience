"""
Timeout/Deadline Pattern Module

Provides timeout and deadline management for async operations.
"""

import asyncio
import functools
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Type

from .events import EventEmitter, PatternType, EventType, TimeoutEvent
from .logging import get_logger
from .config import TimeoutConfig
from .exceptions import (
    OperationTimeoutError,
    TimeoutReason,
    ExceptionHandler,
    ExceptionContext,
    ExceptionConfig,
)

logger = get_logger(__name__)


@dataclass
class TimeoutMetrics:
    """Metrics for timeout operations"""
    total_executions: int = 0
    successful_executions: int = 0
    timed_out_executions: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "timed_out_executions": self.timed_out_executions,
            "total_execution_time": self.total_execution_time,
            "average_execution_time": self.average_execution_time,
            "timeout_rate": (
                self.timed_out_executions / self.total_executions
                if self.total_executions > 0 else 0.0
            ),
        }


class TimeoutManager:
    """
    Manages timeouts for async operations.
    
    Args:
        timeout: Timeout in seconds
        raise_on_timeout: If True, raise OperationTimeoutError; if False, return None
    """
    
    def __init__(
        self,
        config: Optional[TimeoutConfig] = None,
        exceptions: Optional[ExceptionConfig] = None,
    ):
        # Initialize config with defaults
        if config is None:
            config = TimeoutConfig()
        
        self.timeout = config.timeout
        self.raise_on_timeout = config.raise_on_timeout
        self._metrics = TimeoutMetrics()
        self._lock = asyncio.Lock()
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=f"timeout-{id(self)}")
        
        # Initialize exception handling
        if exceptions is None:
            exceptions = ExceptionConfig()
        
        self._exception_handler = ExceptionHandler(
            pattern_name=f"timeout-{id(self)}",
            pattern_type="timeout",
            handled_exceptions=exceptions.handled_exceptions or (Exception,),
            exception_type=exceptions.exception_type or OperationTimeoutError,
            exception_transformer=exceptions.exception_transformer,
            on_exception=exceptions.on_exception,
        )
    
    async def _raise_timeout_error(self, elapsed: float):
        """Raise timeout error using configured exception handler"""
        _, exc = await self._exception_handler.handle_exception(
            reason=TimeoutReason.TIMEOUT_EXCEEDED,
            original_exc=None,
            message=f"Operation exceeded timeout of {self.timeout}s",
            timeout=self.timeout,
            elapsed=elapsed,
        )
        raise exc
    
    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function with timeout.
        
        Args:
            func: Async callable to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        
        Returns:
            Result of function execution or None if timed out and raise_on_timeout=False
        
        Raises:
            OperationTimeoutError: If operation times out and raise_on_timeout=True
        """
        start_time = time.perf_counter()  # Faster than time.time()
        is_coroutine = asyncio.iscoroutinefunction(func)  # Cache check
        
        try:
            if is_coroutine:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.timeout
                )
            else:
                # For sync functions, run in thread with timeout
                result = await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs),
                    timeout=self.timeout
                )
            
            execution_time = time.perf_counter() - start_time
            
            async with self._lock:
                self._metrics.total_executions += 1
                self._metrics.successful_executions += 1
                self._metrics.total_execution_time += execution_time
                # Inline average calculation
                self._metrics.average_execution_time = (
                    self._metrics.total_execution_time / self._metrics.total_executions
                )
            
            # Emit success event
            await self.events.emit(TimeoutEvent(
                pattern_type=PatternType.TIMEOUT,
                event_type=EventType.TIMEOUT_SUCCESS,
                pattern_name=self.events.pattern_name,
                timeout_value=self.timeout,
                elapsed=execution_time,
            ))
            
            return result
            
        except asyncio.TimeoutError:
            execution_time = time.perf_counter() - start_time
            
            async with self._lock:
                self._metrics.total_executions += 1
                self._metrics.timed_out_executions += 1
                self._metrics.total_execution_time += execution_time
                # Inline average calculation
                self._metrics.average_execution_time = (
                    self._metrics.total_execution_time / self._metrics.total_executions
                )
            
            logger.warning(
                f"Operation timed out after {execution_time:.2f}s "
                f"(timeout: {self.timeout}s)"
            )
            
            # Emit timeout occurred event
            await self.events.emit(TimeoutEvent(
                pattern_type=PatternType.TIMEOUT,
                event_type=EventType.TIMEOUT_OCCURRED,
                pattern_name=self.events.pattern_name,
                timeout_value=self.timeout,
                elapsed=execution_time,
            ))
            
            if self.raise_on_timeout:
                await self._raise_timeout_error(execution_time)
            else:
                return None
    
    def get_metrics(self) -> dict[str, Any]:
        """Get timeout metrics"""
        return self._metrics.to_dict()
    
    def reset_metrics(self) -> None:
        """Reset metrics counters"""
        self._metrics = TimeoutMetrics()


class DeadlineManager:
    """
    Manages absolute deadlines for async operations.
    
    Unlike TimeoutManager which uses relative timeouts, DeadlineManager
    works with absolute timestamps, useful for request-scoped deadlines.
    
    Args:
        deadline: Absolute deadline as Unix timestamp
        raise_on_deadline: If True, raise OperationTimeoutError; if False, return None
    """
    
    def __init__(
        self,
        deadline: float,
        raise_on_deadline: bool = True,
        # New exception handling parameters
        exception_type: Optional[Type[Exception]] = None,
        exception_transformer: Optional[Callable[[Exception, ExceptionContext], Exception]] = None,
        on_deadline_exceeded: Optional[Callable[[ExceptionContext], None]] = None,
    ):
        self.deadline = deadline
        self.raise_on_deadline = raise_on_deadline
        
        # Initialize exception handler
        self._exception_handler = ExceptionHandler(
            pattern_name=f"deadline-{id(self)}",
            pattern_type="deadline",
            handled_exceptions=(Exception,),  # Not used for deadline
            exception_type=exception_type or OperationTimeoutError,
            exception_transformer=exception_transformer,
            on_exception=on_deadline_exceeded,
        )
    
    async def _raise_deadline_error(self, message: str):
        """Raise deadline error using configured exception handler"""
        _, exc = await self._exception_handler.handle_exception(
            reason=TimeoutReason.DEADLINE_EXCEEDED,
            original_exc=None,
            message=message,
            deadline=self.deadline,
            current_time=time.time(),
        )
        raise exc
    
    def time_remaining(self) -> float:
        """Get remaining time until deadline"""
        return max(0.0, self.deadline - time.time())
    
    def is_expired(self) -> bool:
        """Check if deadline has passed"""
        return time.time() >= self.deadline
    
    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function with deadline.
        
        Args:
            func: Async callable to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        
        Returns:
            Result of function execution or None if deadline passed
        
        Raises:
            OperationTimeoutError: If deadline is exceeded and raise_on_deadline=True
        """
        if self.is_expired():
            logger.warning("Deadline already expired before execution")
            if self.raise_on_deadline:
                await self._raise_deadline_error("Deadline already expired")
            else:
                return None
        
        timeout = self.time_remaining()
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout
                )
            else:
                result = await asyncio.wait_for(
                    asyncio.to_thread(func, *args, **kwargs),
                    timeout=timeout
                )
            
            return result
            
        except asyncio.TimeoutError:
            logger.warning(
                f"Operation exceeded deadline "
                f"(deadline: {self.deadline}, now: {time.time()})"
            )
            
            if self.raise_on_deadline:
                await self._raise_deadline_error("Operation exceeded deadline")
            else:
                return None


def timeout(
    seconds: float,
    raise_on_timeout: bool = True,
):
    """
    Decorator to add timeout to async functions (convenience pattern).
    
    Creates a new TimeoutManager instance. For reusable instances across
    multiple functions, use @with_timeout_manager(manager) instead.
    
    Example:
        @timeout(5.0)
        async def fetch_data():
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com/data")
                return response.json()
    
    Recommended (instance-based):
        manager = TimeoutManager(config=TimeoutConfig(timeout=5.0))
        
        @with_timeout_manager(manager)
        async def fetch_data():
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com/data")
                return response.json()
    """
    def decorator(func: Callable) -> Callable:
        manager = TimeoutManager(config=TimeoutConfig(timeout=seconds, raise_on_timeout=raise_on_timeout))
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await manager.execute(func, *args, **kwargs)
        
        # Attach manager for metrics access
        wrapper.timeout_manager = manager
        
        return wrapper
    
    return decorator


def with_timeout_manager(manager: TimeoutManager):
    """
    Decorator to use an existing TimeoutManager instance.
    
    Args:
        manager: Existing TimeoutManager instance to use
        
    Example:
        manager = TimeoutManager(config=TimeoutConfig(timeout=5.0))
        
        @with_timeout_manager(manager)
        async def fetch_data():
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com/data")
                return response.json()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await manager.execute(func, *args, **kwargs)
        
        # Attach manager for metrics access
        wrapper.timeout_manager = manager
        
        return wrapper
    
    return decorator


async def with_timeout(
    coro_or_func: Callable,
    timeout_seconds: float,
    *args,
    **kwargs
) -> Any:
    """
    Execute a coroutine or function with timeout.
    
    Convenience function for one-off timeout execution.
    
    Example:
        result = await with_timeout(fetch_data(), 5.0)
        # or
        result = await with_timeout(sync_function, 3.0, arg1, arg2, key=value)
    """
    manager = TimeoutManager(config=TimeoutConfig(timeout=timeout_seconds))
    return await manager.execute(coro_or_func, *args, **kwargs)


async def with_deadline(
    coro_or_func: Callable,
    deadline: float,
    *args,
    **kwargs
) -> Any:
    """
    Execute a coroutine or function with absolute deadline.
    
    Example:
        deadline = time.time() + 10.0  # 10 seconds from now
        result = await with_deadline(fetch_data(), deadline)
    """
    manager = DeadlineManager(deadline=deadline)
    return await manager.execute(coro_or_func, *args, **kwargs)
