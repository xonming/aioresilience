"""
Configuration Classes for Resilience Patterns

Provides clean, reusable configuration objects for all resilience patterns.
"""

from dataclasses import dataclass
from typing import Optional, Tuple, Type, Callable, Dict, Any


@dataclass
class CircuitConfig:
    """
    Configuration for Circuit Breaker pattern.
    
    Args:
        failure_threshold: Number of consecutive failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        success_threshold: Number of successes in half-open state to close circuit
        timeout: Optional timeout in seconds for operations
        half_open_max_calls: Maximum concurrent calls allowed in half-open state
        failure_exceptions: Tuple of exception types that count as failures
        failure_predicate: Optional predicate to determine if exception is a failure
        
    Example:
        >>> config = CircuitConfig(failure_threshold=5, recovery_timeout=60.0)
        >>> circuit = CircuitBreaker(name="api", config=config)
    """
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 2
    timeout: Optional[float] = None
    half_open_max_calls: int = 1
    failure_exceptions: Optional[Tuple[Type[Exception], ...]] = None
    failure_predicate: Optional[Callable[[Exception], bool]] = None
    
    def __post_init__(self):
        """Validate configuration"""
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if self.recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be positive")
        if self.success_threshold < 1:
            raise ValueError("success_threshold must be at least 1")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be positive or None")
        if self.half_open_max_calls < 1:
            raise ValueError("half_open_max_calls must be at least 1")


@dataclass
class BulkheadConfig:
    """
    Configuration for Bulkhead pattern.
    
    Args:
        max_concurrent: Maximum number of concurrent executions
        max_waiting: Maximum number of requests waiting in queue
        timeout: Maximum time to wait for a slot (None = wait indefinitely)
        
    Example:
        >>> config = BulkheadConfig(max_concurrent=10, max_waiting=5)
        >>> bulkhead = Bulkhead(name="db", config=config)
    """
    max_concurrent: int = 10
    max_waiting: int = 0
    timeout: Optional[float] = None
    
    def __post_init__(self):
        """Validate configuration"""
        if self.max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        if self.max_waiting < 0:
            raise ValueError("max_waiting must be non-negative")
        if self.timeout is not None and self.timeout <= 0:
            raise ValueError("timeout must be positive or None")


@dataclass
class TimeoutConfig:
    """
    Configuration for Timeout pattern.
    
    Args:
        timeout: Timeout in seconds
        raise_on_timeout: If True, raise OperationTimeoutError; if False, return None
        
    Example:
        >>> config = TimeoutConfig(timeout=5.0)
        >>> timeout_mgr = TimeoutManager(config=config)
    """
    timeout: float = 30.0
    raise_on_timeout: bool = True
    
    def __post_init__(self):
        """Validate configuration"""
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")


@dataclass
class BackpressureConfig:
    """
    Configuration for Backpressure pattern.
    
    Args:
        max_pending: Maximum pending items (hard limit)
        high_water_mark: Start applying backpressure at this level
        low_water_mark: Stop applying backpressure at this level
        
    Example:
        >>> config = BackpressureConfig(max_pending=1000, high_water_mark=800)
        >>> bp = BackpressureManager(config=config)
    """
    max_pending: int = 1000
    high_water_mark: int = 800
    low_water_mark: int = 200
    
    def __post_init__(self):
        """Validate configuration"""
        if self.max_pending < 1:
            raise ValueError("max_pending must be at least 1")
        if self.high_water_mark > self.max_pending:
            raise ValueError("high_water_mark cannot exceed max_pending")
        if self.low_water_mark > self.high_water_mark:
            raise ValueError("low_water_mark cannot exceed high_water_mark")


@dataclass
class LoadSheddingConfig:
    """
    Configuration for Load Shedding pattern.
    
    Args:
        max_requests: Maximum concurrent requests
        max_queue_depth: Maximum queue depth
        
    Example:
        >>> config = LoadSheddingConfig(max_requests=1000)
        >>> shedder = BasicLoadShedder(config=config)
    """
    max_requests: int = 1000
    max_queue_depth: int = 500
    
    def __post_init__(self):
        """Validate configuration"""
        if self.max_requests < 1:
            raise ValueError("max_requests must be at least 1")
        if self.max_queue_depth < 0:
            raise ValueError("max_queue_depth must be non-negative")


@dataclass
class RetryConfig:
    """
    Configuration for Retry pattern.
    
    Args:
        max_attempts: Maximum number of retry attempts (including initial attempt)
        initial_delay: Initial delay in seconds before first retry
        max_delay: Maximum delay in seconds between retries
        backoff_multiplier: Multiplier for exponential/linear backoff
        strategy: Retry strategy (CONSTANT, LINEAR, EXPONENTIAL)
        jitter: Add randomization to delays (0.0 to 1.0)
        retry_on_exceptions: Tuple of exception types to retry on
        retry_on_result: Optional callable to determine if result should trigger retry
        exception_strategies: Per-exception retry strategies
        on_retry: Callback when a retry is attempted
        on_success_after_retry: Callback when operation succeeds after retries
        on_exhausted: Callback when all retries are exhausted
        
    Example:
        >>> from aioresilience.retry import RetryStrategy
        >>> config = RetryConfig(
        ...     max_attempts=5,
        ...     strategy=RetryStrategy.EXPONENTIAL,
        ...     initial_delay=1.0,
        ...     on_retry=lambda ctx: print(f"Retry {ctx.metadata['attempt']}")
        ... )
        >>> retry = RetryPolicy(config=config)
    """
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    strategy: int = 2  # RetryStrategy.EXPONENTIAL
    jitter: float = 0.1
    retry_on_exceptions: Optional[Tuple[Type[Exception], ...]] = None
    retry_on_result: Optional[Callable[[Any], bool]] = None
    exception_strategies: Optional[Dict[Type[Exception], Dict[str, Any]]] = None
    # Pattern-specific callbacks
    on_retry: Optional[Callable[[Any], None]] = None  # ExceptionContext
    on_success_after_retry: Optional[Callable[[Any], None]] = None
    on_exhausted: Optional[Callable[[Any], None]] = None
    
    def __post_init__(self):
        """Validate configuration"""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay < 0:
            raise ValueError("initial_delay must be non-negative")
        if self.max_delay < self.initial_delay:
            raise ValueError("max_delay must be >= initial_delay")
        if self.backoff_multiplier <= 0:
            raise ValueError("backoff_multiplier must be positive")
        if not 0.0 <= self.jitter <= 1.0:
            raise ValueError("jitter must be between 0.0 and 1.0")


@dataclass
class RateLimitConfig:
    """
    Configuration for Rate Limiting pattern.
    
    Args:
        name: Name for this rate limiter
        max_limiters: Maximum number of limiters to cache (LRU eviction)
        
    Example:
        >>> config = RateLimitConfig(name="api", max_limiters=10000)
        >>> limiter = LocalRateLimiter(config=config)
    """
    name: str = "default"
    max_limiters: int = 10000
    
    def __post_init__(self):
        """Validate configuration"""
        if not self.name or not self.name.strip():
            raise ValueError("name must be a non-empty string")
        if self.max_limiters < 1:
            raise ValueError("max_limiters must be at least 1")


@dataclass
class FallbackConfig:
    """
    Configuration for Fallback pattern.
    
    Args:
        fallback: Fallback value, callable, or coroutine
        fallback_on_exceptions: Tuple of exception types that trigger fallback
        reraise_on_fallback_failure: If True, reraise if fallback also fails
        
    Example:
        >>> config = FallbackConfig(
        ...     fallback=lambda: "default value",
        ...     fallback_on_exceptions=(ValueError, KeyError)
        ... )
        >>> handler = FallbackHandler(config=config)
    """
    fallback: Optional[Any] = None
    fallback_on_exceptions: Optional[Tuple[Type[Exception], ...]] = None
    reraise_on_fallback_failure: bool = True


@dataclass
class AdaptiveConcurrencyConfig:
    """
    Configuration for the AdaptiveConcurrencyLimiter using an AIMD algorithm.

    This config controls how quickly the limiter reacts to success/failure patterns
    and enforces safe bounds on concurrency.

    Args:
        initial_limit:
            Initial allowed concurrency. Must be between min_limit and max_limit.
        min_limit:
            Minimum allowed concurrency (hard lower bound).
        max_limit:
            Maximum allowed concurrency (hard upper bound).
        increase_rate:
            Additive increase applied to the current_limit when the observed
            success rate is above success_threshold.
        decrease_factor:
            Multiplicative factor (0.0-1.0) applied to current_limit when the
            observed success rate is below failure_threshold.
        measurement_window:
            Number of completed requests after which success/failure ratios are
            evaluated and the AIMD adjustment is applied.
        success_threshold:
            Success-rate threshold (0.0-1.0) above which we consider the system
            healthy enough to increase concurrency.
        failure_threshold:
            Success-rate threshold (0.0-1.0) at or below which we consider the
            system unhealthy and decrease concurrency.

    Example:
        >>> from aioresilience import AdaptiveConcurrencyLimiter
        >>> cfg = AdaptiveConcurrencyConfig(
        ...     initial_limit=100,
        ...     min_limit=10,
        ...     max_limit=1000,
        ...     increase_rate=1.0,
        ...     decrease_factor=0.9,
        ...     measurement_window=100,
        ...     success_threshold=0.95,
        ...     failure_threshold=0.80,
        ... )
        >>> limiter = AdaptiveConcurrencyLimiter("api-limiter", cfg)

    """
    initial_limit: int = 100
    min_limit: int = 10
    max_limit: int = 1000
    increase_rate: float = 1.0
    decrease_factor: float = 0.9
    measurement_window: int = 100
    success_threshold: float = 0.95
    failure_threshold: float = 0.80
    
    def __post_init__(self):
        """Validate configuration for internal consistency."""
        if self.initial_limit < 1:
            raise ValueError("initial_limit must be at least 1")
        if self.min_limit < 1:
            raise ValueError("min_limit must be at least 1")
        if self.max_limit < self.min_limit:
            raise ValueError("max_limit must be >= min_limit")
        if not (self.min_limit <= self.initial_limit <= self.max_limit):
            raise ValueError("initial_limit must be between min_limit and max_limit")
        if self.increase_rate <= 0:
            raise ValueError("increase_rate must be positive")
        if not 0 < self.decrease_factor < 1:
            raise ValueError("decrease_factor must be between 0 and 1")
        if self.measurement_window < 1:
            raise ValueError("measurement_window must be at least 1")
        if not 0 <= self.success_threshold <= 1:
            raise ValueError("success_threshold must be between 0 and 1")
        if not 0 <= self.failure_threshold <= 1:
            raise ValueError("failure_threshold must be between 0 and 1")
        if self.failure_threshold >= self.success_threshold:
            raise ValueError("failure_threshold must be less than success_threshold")
