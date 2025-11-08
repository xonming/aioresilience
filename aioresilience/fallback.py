"""
Fallback Pattern Module

Provides fallback mechanisms to gracefully handle failures with alternative responses.
"""

import asyncio
import functools
from dataclasses import dataclass
from typing import Callable, TypeVar, Any, Optional, Union, Type
from functools import wraps

from .events import EventEmitter, PatternType, EventType, FallbackEvent
from .logging import get_logger
from .config import FallbackConfig
from .exceptions import (
    ExceptionConfig,
    ExceptionHandler,
    ExceptionContext,
    FallbackFailedError,
    FallbackReason,
)

logger = get_logger(__name__)


@dataclass
class FallbackMetrics:
    """Metrics for fallback operations"""
    total_executions: int = 0
    successful_executions: int = 0
    fallback_executions: int = 0
    failed_executions: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "total_executions": self.total_executions,
            "successful_executions": self.successful_executions,
            "fallback_executions": self.fallback_executions,
            "failed_executions": self.failed_executions,
            "fallback_rate": (
                self.fallback_executions / self.total_executions
                if self.total_executions > 0 else 0.0
            ),
            "failure_rate": (
                self.failed_executions / self.total_executions
                if self.total_executions > 0 else 0.0
            ),
        }


class FallbackHandler:
    """
    Handles fallback logic for failed operations.
    
    Args:
        fallback: Fallback value, callable, or coroutine
        fallback_on_exceptions: Tuple of exception types that trigger fallback
        reraise_on_fallback_failure: If True, reraise if fallback also fails
    """
    
    def __init__(
        self,
        config: Optional[FallbackConfig] = None,
        exceptions: Optional[ExceptionConfig] = None,
    ):
        # Initialize config with defaults
        if config is None:
            config = FallbackConfig()
        
        # Initialize exception handling
        if exceptions is None:
            exceptions = ExceptionConfig()
        
        self.fallback = config.fallback
        self.fallback_on_exceptions = config.fallback_on_exceptions or (Exception,)
        self.reraise_on_fallback_failure = config.reraise_on_fallback_failure
        self._metrics = FallbackMetrics()
        self._lock = asyncio.Lock()
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=f"fallback-{id(self)}")
        
        # Exception handler for when all fallbacks fail
        self._exception_handler = ExceptionHandler(
            pattern_name=f"fallback-{id(self)}",
            pattern_type="fallback",
            handled_exceptions=exceptions.handled_exceptions or (Exception,),
            exception_type=exceptions.exception_type or FallbackFailedError,
            exception_transformer=exceptions.exception_transformer,
            on_exception=exceptions.on_exception,
        )
    
    async def _execute_fallback(self, *args, **kwargs) -> Any:
        """Execute the fallback logic"""
        if callable(self.fallback):
            if asyncio.iscoroutinefunction(self.fallback):
                return await self.fallback(*args, **kwargs)
            else:
                # Sync callable
                return self.fallback(*args, **kwargs)
        else:
            # Static value
            return self.fallback
    
    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with fallback on failure.
        
        Args:
            func: Async or sync callable to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        
        Returns:
            Result of function execution or fallback value
        
        Raises:
            Exception: If both primary and fallback fail and reraise_on_fallback_failure=True
        """
        async with self._lock:
            self._metrics.total_executions += 1
        
        # Try primary execution
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)
            
            async with self._lock:
                self._metrics.successful_executions += 1
            
            return result
            
        except self.fallback_on_exceptions as e:
            logger.info(
                f"Primary execution failed with {type(e).__name__}: {e}, "
                f"executing fallback"
            )
            
            # Emit primary failed event
            await self.events.emit(FallbackEvent(
                pattern_type=PatternType.FALLBACK,
                event_type=EventType.PRIMARY_FAILED,
                pattern_name=self.events.pattern_name,
                primary_error=str(e),
            ))
            
            # Try fallback
            try:
                result = await self._execute_fallback(*args, **kwargs)
                
                async with self._lock:
                    self._metrics.fallback_executions += 1
                
                # Emit fallback executed event
                await self.events.emit(FallbackEvent(
                    pattern_type=PatternType.FALLBACK,
                    event_type=EventType.FALLBACK_EXECUTED,
                    pattern_name=self.events.pattern_name,
                    primary_error=str(e),
                    fallback_value=result,
                ))
                
                logger.info("Fallback executed successfully")
                return result
                
            except Exception as fallback_error:
                async with self._lock:
                    self._metrics.failed_executions += 1
                
                logger.error(
                    f"Fallback also failed with {type(fallback_error).__name__}: {fallback_error}"
                )
                
                if self.reraise_on_fallback_failure:
                    # Use exception handler to raise custom exception
                    _, exc = await self._exception_handler.handle_exception(
                        reason=FallbackReason.ALL_FALLBACKS_FAILED,
                        original_exc=fallback_error,
                        message=f"All fallback attempts failed. Original error: {e}, Fallback error: {fallback_error}",
                        original_error=str(e),
                        fallback_error=str(fallback_error),
                    )
                    raise exc
                else:
                    logger.warning("Suppressing fallback failure, returning None")
                    return None
    
    def get_metrics(self) -> dict[str, Any]:
        """Get fallback metrics"""
        return self._metrics.to_dict()
    
    def reset_metrics(self) -> None:
        """Reset metrics counters"""
        self._metrics = FallbackMetrics()


class ChainedFallback:
    """
    Chain multiple fallback strategies.
    
    Tries each fallback in order until one succeeds.
    
    Args:
        *fallbacks: Sequence of fallback values or callables to try in order
        fallback_on_exceptions: Tuple of exception types that trigger fallback
    """
    
    def __init__(
        self,
        *fallbacks: Union[Any, Callable],
        fallback_on_exceptions: tuple[Type[Exception], ...] = (Exception,),
    ):
        if not fallbacks:
            raise ValueError("At least one fallback must be provided")
        
        self.fallbacks = fallbacks
        self.fallback_on_exceptions = fallback_on_exceptions
        self._metrics = FallbackMetrics()
        self._lock = asyncio.Lock()
    
    async def _try_fallback(self, fallback: Union[Any, Callable], *args, **kwargs) -> Any:
        """Try a single fallback"""
        if callable(fallback):
            if asyncio.iscoroutinefunction(fallback):
                return await fallback(*args, **kwargs)
            else:
                return fallback(*args, **kwargs)
        else:
            return fallback
    
    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with chained fallbacks.
        
        Args:
            func: Async or sync callable to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        
        Returns:
            Result of function execution or first successful fallback
        
        Raises:
            Exception: If all fallbacks fail
        """
        async with self._lock:
            self._metrics.total_executions += 1
        
        # Try primary execution
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)
            
            async with self._lock:
                self._metrics.successful_executions += 1
            
            return result
            
        except self.fallback_on_exceptions as primary_error:
            logger.info(
                f"Primary execution failed with {type(primary_error).__name__}: {primary_error}"
            )
            
            # Try each fallback in sequence
            for i, fallback in enumerate(self.fallbacks, 1):
                try:
                    logger.info(f"Trying fallback {i}/{len(self.fallbacks)}")
                    result = await self._try_fallback(fallback, *args, **kwargs)
                    
                    async with self._lock:
                        self._metrics.fallback_executions += 1
                    
                    logger.info(f"Fallback {i} succeeded")
                    return result
                    
                except Exception as fallback_error:
                    logger.warning(
                        f"Fallback {i} failed with {type(fallback_error).__name__}: {fallback_error}"
                    )
                    if i == len(self.fallbacks):
                        # Last fallback failed
                        async with self._lock:
                            self._metrics.failed_executions += 1
                        logger.error("All fallbacks exhausted")
                        raise
                    continue
    
    def get_metrics(self) -> dict[str, Any]:
        """Get fallback metrics"""
        return self._metrics.to_dict()
    
    def reset_metrics(self) -> None:
        """Reset metrics counters"""
        self._metrics = FallbackMetrics()


def fallback(
    fallback_value: Union[Any, Callable],
    fallback_on_exceptions: tuple[Type[Exception], ...] = (Exception,),
    reraise_on_fallback_failure: bool = True,
):
    """
    Decorator to add fallback logic to async functions (convenience pattern).
    
    Creates a new FallbackHandler instance. For reusable instances across
    multiple functions, use @with_fallback_handler(handler) instead.
    
    Example:
        # Static fallback value
        @fallback([])
        async def fetch_items():
            response = await api.get_items()
            return response.json()
        
        # Fallback function
        @fallback(lambda: {"status": "unavailable"})
        async def get_status():
            return await api.get_status()
    
    Recommended (instance-based):
        handler = FallbackHandler(config=FallbackConfig(fallback=[]))
        
        @with_fallback_handler(handler)
        async def fetch_items():
            response = await api.get_items()
            return response.json()
    """
    def decorator(func: Callable) -> Callable:
        handler = FallbackHandler(
            config=FallbackConfig(
                fallback=fallback_value,
                fallback_on_exceptions=fallback_on_exceptions,
                reraise_on_fallback_failure=reraise_on_fallback_failure,
            )
        )
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await handler.execute(func, *args, **kwargs)
        
        # Attach handler for metrics access
        wrapper.fallback_handler = handler
        
        return wrapper
    
    return decorator


def chained_fallback(
    *fallbacks: Union[Any, Callable],
    fallback_on_exceptions: tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator to add chained fallback logic to async functions.
    
    Example:
        @chained_fallback(
            get_from_cache,
            get_from_backup_api,
            {"data": "default"},
        )
        async def fetch_critical_data():
            return await primary_api.fetch()
    """
    def decorator(func: Callable) -> Callable:
        handler = ChainedFallback(
            *fallbacks,
            fallback_on_exceptions=fallback_on_exceptions,
        )
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await handler.execute(func, *args, **kwargs)
        
        # Attach handler for metrics access
        wrapper.fallback_handler = handler
        
        return wrapper
    
    return decorator


def with_fallback_handler(handler: FallbackHandler):
    """
    Decorator to use an existing FallbackHandler instance.
    
    Args:
        handler: Existing FallbackHandler instance to use
        
    Example:
        handler = FallbackHandler(config=FallbackConfig(fallback={"default": "data"}))
        
        @with_fallback_handler(handler)
        async def fetch_data():
            return await api.fetch()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await handler.execute(func, *args, **kwargs)
        
        # Attach handler for metrics access
        wrapper.fallback_handler = handler
        
        return wrapper
    
    return decorator


async def with_fallback(
    func: Callable,
    fallback_value: Union[Any, Callable],
    *args,
    **kwargs
) -> Any:
    """
    Execute a function with fallback.
    
    Convenience function for one-off fallback execution.
    
    Example:
        result = await with_fallback(
            fetch_data,
            fallback_value=[],
            user_id=123
        )
    """
    handler = FallbackHandler(config=FallbackConfig(fallback=fallback_value))
    return await handler.execute(func, *args, **kwargs)
