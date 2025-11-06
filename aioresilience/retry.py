"""
Retry Pattern Module

Provides retry logic with exponential backoff, jitter, and configurable retry policies.
"""

import asyncio
import functools
import random
import time
from typing import Optional, Callable, TypeVar, Any, Union, Type
from enum import Enum
from dataclasses import dataclass, field

from .events import EventEmitter, PatternType, EventType, RetryEvent
from .logging import get_logger

logger = get_logger(__name__)


class RetryStrategy(Enum):
    """Retry backoff strategies"""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    CONSTANT = "constant"


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
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        jitter: float = 0.1,
        retry_on_exceptions: tuple[Type[Exception], ...] = (Exception,),
        retry_on_result: Optional[Callable[[Any], bool]] = None,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if initial_delay < 0:
            raise ValueError("initial_delay must be non-negative")
        if max_delay < initial_delay:
            raise ValueError("max_delay must be >= initial_delay")
        if backoff_multiplier <= 0:
            raise ValueError("backoff_multiplier must be positive")
        if strategy == RetryStrategy.EXPONENTIAL and backoff_multiplier < 1.0:
            raise ValueError("backoff_multiplier must be >= 1.0 for exponential strategy")
        if not 0.0 <= jitter <= 1.0:
            raise ValueError("jitter must be between 0.0 and 1.0")
        
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.strategy = strategy
        self.jitter = jitter
        self.retry_on_exceptions = retry_on_exceptions
        self.retry_on_result = retry_on_result
        self._metrics = RetryMetrics()
        self._lock = asyncio.Lock()
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=f"retry-{id(self)}")
    
    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt number"""
        if self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.initial_delay * (self.backoff_multiplier ** (attempt - 1))
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.initial_delay + (self.backoff_multiplier * (attempt - 1))
        else:  # CONSTANT
            delay = self.initial_delay
        
        # Cap at max_delay
        delay = min(delay, self.max_delay)
        
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
        is_coroutine = asyncio.iscoroutinefunction(func)
        
        for attempt in range(1, self.max_attempts + 1):
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
                
                return result
                
            except self.retry_on_exceptions as e:
                last_exception = e
                async with self._lock:
                    self._metrics.total_attempts += 1
                    self._metrics.failed_attempts += 1
                    self._metrics.last_error = e
                
                if attempt < self.max_attempts:
                    delay = self._calculate_delay(attempt)
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
                        f"All {self.max_attempts} attempts failed. Last error: {type(e).__name__}: {e}"
                    )
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
            max_attempts=max_attempts,
            initial_delay=initial_delay,
            max_delay=max_delay,
            backoff_multiplier=backoff_multiplier,
            strategy=strategy,
            jitter=jitter,
            retry_on_exceptions=retry_on_exceptions,
            retry_on_result=retry_on_result,
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
        return RetryPolicy(max_attempts=3, initial_delay=1.0)
    
    @staticmethod
    def aggressive() -> RetryPolicy:
        """Aggressive retry: 5 attempts, fast exponential backoff"""
        return RetryPolicy(
            max_attempts=5,
            initial_delay=0.1,
            max_delay=10.0,
            backoff_multiplier=2.0,
        )
    
    @staticmethod
    def conservative() -> RetryPolicy:
        """Conservative retry: 3 attempts, linear backoff with high jitter"""
        return RetryPolicy(
            max_attempts=3,
            initial_delay=2.0,
            max_delay=30.0,
            strategy=RetryStrategy.LINEAR,
            jitter=0.3,
        )
    
    @staticmethod
    def network() -> RetryPolicy:
        """Network-oriented retry: handles connection errors"""
        return RetryPolicy(
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
