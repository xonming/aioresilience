"""
Retry Pattern Module

Provides retry logic with exponential backoff, jitter, and configurable retry policies.
"""

import asyncio
import functools
import random
import time
from typing import Any, Callable, Optional, Tuple, Type, Dict
from dataclasses import dataclass, field
from enum import IntEnum

from .events import EventEmitter, PatternType, EventType, RetryEvent
from .logging import get_logger
from .config import RetryConfig
from .exceptions import (
    RetryReason,
    ExceptionHandler,
    ExceptionContext,
    ExceptionConfig,
)

logger = get_logger(__name__)


class RetryStrategy(IntEnum):
    """Retry backoff strategies (IntEnum for performance)"""
    CONSTANT = 0      # Constant delay (simplest, check first)
    LINEAR = 1        # Linear backoff
    EXPONENTIAL = 2   # Exponential backoff


@dataclass
class RetryMetrics:
    """Metrics for retry operations"""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_delay: float = 0.0
    last_error: Optional[Exception] = None
    retries_exhausted: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "total_attempts": self.total_attempts,
            "successful_attempts": self.successful_attempts,
            "failed_attempts": self.failed_attempts,
            "total_delay": self.total_delay,
            "last_error": str(self.last_error) if self.last_error else None,
            "retries_exhausted": self.retries_exhausted,
            "success_rate": (
                self.successful_attempts / self.total_attempts
                if self.total_attempts > 0 else 0.0
            ),
        }


class RetryPolicy:
    """
    Retry policy with configurable backoff strategies.
    
    Args:
        max_attempts: Maximum number of retry attempts (including initial attempt)
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds between retries
        backoff_multiplier: Multiplier for exponential/linear backoff
        strategy: Retry strategy (exponential, linear, constant)
        jitter: Add randomization to delays (0.0 to 1.0)
        retry_on_exceptions: Tuple of exception types to retry on
        retry_on_result: Optional callable to determine if result should trigger retry
    """
    
    def __init__(
        self,
        config: Optional[RetryConfig] = None,
        exceptions: Optional[ExceptionConfig] = None,
    ):
        # Initialize config with defaults
        if config is None:
            config = RetryConfig()
        
        # Validate strategy if it's an int (from config)
        if isinstance(config.strategy, int):
            # Validate it's a valid RetryStrategy value
            if config.strategy == RetryStrategy.EXPONENTIAL and config.backoff_multiplier < 1.0:
                raise ValueError("backoff_multiplier must be >= 1.0 for exponential strategy")
        
        self.max_attempts = config.max_attempts
        self.initial_delay = config.initial_delay
        self.max_delay = config.max_delay
        self.backoff_multiplier = config.backoff_multiplier
        self.strategy = RetryStrategy(config.strategy)  # Convert int to enum
        self.jitter = config.jitter
        self.retry_on_exceptions = config.retry_on_exceptions or (Exception,)
        self.retry_on_result = config.retry_on_result
        self._metrics = RetryMetrics()
        self._lock = asyncio.Lock()
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=f"retry-{id(self)}")
        
        # Store callbacks from config
        self._on_retry = config.on_retry
        self._on_success_after_retry = config.on_success_after_retry
        self._on_exhausted = config.on_exhausted
        
        # Handle per-exception strategies from config
        self._exception_strategies = config.exception_strategies or {}
        self._max_possible_attempts = config.max_attempts  # Track maximum attempts across all strategies
        
        if config.exception_strategies:
            for exc_type, exc_config in config.exception_strategies.items():
                exc_max_attempts = exc_config.get('max_attempts', config.max_attempts)
                self._exception_strategies[exc_type] = {
                    'max_attempts': exc_max_attempts,
                    'initial_delay': exc_config.get('initial_delay', config.initial_delay),
                    'max_delay': exc_config.get('max_delay', config.max_delay),
                    'backoff_multiplier': exc_config.get('backoff_multiplier', config.backoff_multiplier),
                    'strategy': exc_config.get('strategy', config.strategy),
                }
                # Track the maximum attempts across all exception types
                self._max_possible_attempts = max(self._max_possible_attempts, exc_max_attempts)
                
                # Add to retry_on_exceptions if not already there
                if exc_type not in self.retry_on_exceptions:
                    self.retry_on_exceptions = self.retry_on_exceptions + (exc_type,)
    
    def _get_strategy_for_exception(self, exc: Exception) -> Dict[str, Any]:
        """Get retry strategy configuration for a specific exception type"""
        # Check if there's a per-exception strategy
        for exc_type, config in self._exception_strategies.items():
            if isinstance(exc, exc_type):
                return config
        
        # Fall back to default configuration
        return {
            'max_attempts': self.max_attempts,
            'initial_delay': self.initial_delay,
            'max_delay': self.max_delay,
            'backoff_multiplier': self.backoff_multiplier,
            'strategy': self.strategy,
        }
    
    def _calculate_delay(self, attempt: int, strategy_config: Optional[Dict[str, Any]] = None) -> float:
        """Calculate delay for given attempt number using provided or default strategy"""
        if strategy_config is None:
            strategy_config = {
                'initial_delay': self.initial_delay,
                'backoff_multiplier': self.backoff_multiplier,
                'max_delay': self.max_delay,
                'strategy': self.strategy,
            }
        
        initial_delay = strategy_config['initial_delay']
        backoff_multiplier = strategy_config['backoff_multiplier']
        max_delay = strategy_config['max_delay']
        strategy = strategy_config['strategy']
        
        if strategy == RetryStrategy.EXPONENTIAL:
            delay = initial_delay * (backoff_multiplier ** (attempt - 1))
        elif strategy == RetryStrategy.LINEAR:
            delay = initial_delay + (backoff_multiplier * (attempt - 1))
        else:  # CONSTANT
            delay = initial_delay
        
        # Cap at max_delay
        delay = min(delay, max_delay)
        
        # Add jitter
        if self.jitter > 0:
            jitter_amount = delay * self.jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0, delay)
    
    def _should_retry_on_result(self, result: Any) -> bool:
        """Check if result should trigger a retry"""
        if self.retry_on_result is None:
            return False
        try:
            return self.retry_on_result(result)
        except Exception as e:
            logger.warning(f"Error in retry_on_result callback: {e}")
            return False
    
    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function with retry logic.
        
        Args:
            func: Async or sync callable to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        
        Returns:
            Result of successful function execution
        
        Raises:
            Last exception if all retries exhausted
        """
        last_exception = None
        
        # Cache coroutine check to avoid repeated inspect calls (5-6μs each)
        func_id = id(func)
        if not hasattr(self, '_coro_cache'):
            self._coro_cache = {}
        
        if func_id not in self._coro_cache:
            self._coro_cache[func_id] = asyncio.iscoroutinefunction(func)
        
        is_coroutine = self._coro_cache[func_id]
        
        # Use max possible attempts to handle per-exception strategies
        for attempt in range(1, self._max_possible_attempts + 1):
            try:
                # Execute function
                if is_coroutine:
                    result = await func(*args, **kwargs)
                else:
                    result = await asyncio.to_thread(func, *args, **kwargs)
                
                # Check if result should trigger retry
                if self._should_retry_on_result(result):
                    if attempt < self.max_attempts:
                        delay = self._calculate_delay(attempt)
                        logger.info(
                            f"Retry condition met on attempt {attempt}/{self.max_attempts}, "
                            f"retrying in {delay:.2f}s"
                        )
                        async with self._lock:
                            self._metrics.total_attempts += 1
                            self._metrics.total_delay += delay
                        await asyncio.sleep(delay)
                        continue
                    else:
                        async with self._lock:
                            self._metrics.retries_exhausted += 1
                        logger.warning(
                            f"Retry condition met but max attempts ({self.max_attempts}) reached"
                        )
                
                # Success
                async with self._lock:
                    self._metrics.total_attempts += 1
                    self._metrics.successful_attempts += 1
                
                # Emit success event
                await self.events.emit(RetryEvent(
                    pattern_type=PatternType.RETRY,
                    event_type=EventType.RETRY_SUCCESS,
                    pattern_name=self.events.pattern_name,
                    attempt=attempt,
                    max_attempts=self.max_attempts,
                ))
                
                # Call on_success_after_retry callback if this wasn't the first attempt
                if attempt > 1 and self._on_success_after_retry:
                    try:
                        ctx = ExceptionContext(
                            pattern_name=self.events.pattern_name,
                            pattern_type="retry",
                            reason=RetryReason.EXHAUSTED,  # Placeholder
                            original_exception=None,
                            metadata={
                                'attempt': attempt,
                                'max_attempts': self.max_attempts,
                            }
                        )
                        if asyncio.iscoroutinefunction(self._on_success_after_retry):
                            await self._on_success_after_retry(ctx)
                        else:
                            self._on_success_after_retry(ctx)
                    except Exception as callback_error:
                        logger.warning(f"Error in on_success_after_retry callback: {callback_error}")
                
                return result
                
            except self.retry_on_exceptions as e:
                last_exception = e
                async with self._lock:
                    self._metrics.total_attempts += 1
                    self._metrics.failed_attempts += 1
                    self._metrics.last_error = e
                
                # Get strategy for this specific exception type
                strategy_config = self._get_strategy_for_exception(e)
                max_attempts_for_exc = strategy_config['max_attempts']
                
                if attempt < max_attempts_for_exc:
                    delay = self._calculate_delay(attempt, strategy_config)
                    logger.info(
                        f"Attempt {attempt}/{self.max_attempts} failed with {type(e).__name__}: {e}, "
                        f"retrying in {delay:.2f}s"
                    )
                    async with self._lock:
                        self._metrics.total_delay += delay
                    
                    # Emit retry attempt event
                    await self.events.emit(RetryEvent(
                        pattern_type=PatternType.RETRY,
                        event_type=EventType.RETRY_ATTEMPT,
                        pattern_name=self.events.pattern_name,
                        attempt=attempt + 1,  # Next attempt
                        max_attempts=self.max_attempts,
                        delay=delay,
                        error=str(e),
                    ))
                    
                    # Call on_retry callback
                    if self._on_retry:
                        try:
                            ctx = ExceptionContext(
                                pattern_name=self.events.pattern_name,
                                pattern_type="retry",
                                reason=RetryReason.EXHAUSTED,  # Placeholder
                                original_exception=e,
                                metadata={
                                    'attempt': attempt,
                                    'max_attempts': max_attempts_for_exc,
                                    'delay': delay,
                                }
                            )
                            if asyncio.iscoroutinefunction(self._on_retry):
                                await self._on_retry(ctx)
                            else:
                                self._on_retry(ctx)
                        except Exception as callback_error:
                            logger.warning(f"Error in on_retry callback: {callback_error}")
                    
                    await asyncio.sleep(delay)
                else:
                    async with self._lock:
                        self._metrics.retries_exhausted += 1
                    
                    # Emit retries exhausted event
                    await self.events.emit(RetryEvent(
                        pattern_type=PatternType.RETRY,
                        event_type=EventType.RETRY_EXHAUSTED,
                        pattern_name=self.events.pattern_name,
                        attempt=attempt,
                        max_attempts=self.max_attempts,
                        error=str(e),
                    ))
                    
                    logger.error(
                        f"All {max_attempts_for_exc} attempts failed. Last error: {type(e).__name__}: {e}"
                    )
                    
                    # Call on_exhausted callback
                    if self._on_exhausted:
                        try:
                            ctx = ExceptionContext(
                                pattern_name=self.events.pattern_name,
                                pattern_type="retry",
                                reason=RetryReason.EXHAUSTED,
                                original_exception=e,
                                metadata={
                                    'attempt': attempt,
                                    'max_attempts': max_attempts_for_exc,
                                }
                            )
                            if asyncio.iscoroutinefunction(self._on_exhausted):
                                await self._on_exhausted(ctx)
                            else:
                                self._on_exhausted(ctx)
                        except Exception as callback_error:
                            logger.warning(f"Error in on_exhausted callback: {callback_error}")
                    
                    raise
            
            except Exception as e:
                # Non-retryable exception
                async with self._lock:
                    self._metrics.total_attempts += 1
                    self._metrics.failed_attempts += 1
                    self._metrics.last_error = e
                logger.error(f"Non-retryable exception: {type(e).__name__}: {e}")
                raise
        
        # Should not reach here, but raise last exception if we do
        if last_exception:
            raise last_exception
    
    def get_metrics(self) -> dict[str, Any]:
        """Get retry metrics"""
        return self._metrics.to_dict()
    
    def reset_metrics(self) -> None:
        """Reset metrics counters"""
        self._metrics = RetryMetrics()


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_multiplier: float = 2.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    jitter: float = 0.1,
    retry_on_exceptions: tuple[Type[Exception], ...] = (Exception,),
    retry_on_result: Optional[Callable[[Any], bool]] = None,
):
    """
    Decorator to add retry logic to async functions.
    
    Example:
        @retry(max_attempts=5, initial_delay=0.5, strategy=RetryStrategy.EXPONENTIAL)
        async def fetch_data():
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com/data")
                return response.json()
    """
    def decorator(func: Callable) -> Callable:
        policy = RetryPolicy(
            config=RetryConfig(
                max_attempts=max_attempts,
                initial_delay=initial_delay,
                max_delay=max_delay,
                backoff_multiplier=backoff_multiplier,
                strategy=strategy,
                jitter=jitter,
                retry_on_exceptions=retry_on_exceptions,
                retry_on_result=retry_on_result,
            )
        )
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await policy.execute(func, *args, **kwargs)
        
        # Attach policy for metrics access
        wrapper.retry_policy = policy
        
        return wrapper
    
    return decorator


# Predefined retry policies for common scenarios
class RetryPolicies:
    """Common retry policy configurations"""
    
    @staticmethod
    def default() -> RetryPolicy:
        """Default retry policy: 3 attempts, exponential backoff"""
        return RetryPolicy(config=RetryConfig(max_attempts=3, initial_delay=1.0))
    
    @staticmethod
    def aggressive() -> RetryPolicy:
        """Aggressive retry: 5 attempts, fast exponential backoff"""
        return RetryPolicy(
            config=RetryConfig(
                max_attempts=5,
                initial_delay=0.1,
                max_delay=10.0,
                backoff_multiplier=2.0,
            )
        )
    
    @staticmethod
    def conservative() -> RetryPolicy:
        """Conservative retry: 3 attempts, linear backoff with high jitter"""
        return RetryPolicy(
            config=RetryConfig(
                max_attempts=3,
                initial_delay=2.0,
                max_delay=30.0,
                strategy=RetryStrategy.LINEAR,
                jitter=0.3,
            )
        )
    
    @staticmethod
    def network() -> RetryPolicy:
        """Network-oriented retry: handles connection errors"""
        return RetryPolicy(
            config=RetryConfig(
                max_attempts=4,
                initial_delay=0.5,
                max_delay=15.0,
                backoff_multiplier=2.5,
                retry_on_exceptions=(
                    ConnectionError,
                    TimeoutError,
                    OSError,
                ),
            )
        )
