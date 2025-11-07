"""
Adaptive Concurrency Limiter

Implements an AIMD (Additive Increase, Multiplicative Decrease) algorithm to
dynamically adjust concurrency limits based on observed success rates.

Usage is configuration-driven and consistent with other aioresilience patterns:
- Initialize an AdaptiveConcurrencyConfig with your desired parameters.
- Pass it to AdaptiveConcurrencyLimiter together with a name.
- Use either the async context manager protocol or explicit acquire/release calls.

Dependencies: None (pure Python async).
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from .events import EventEmitter, PatternType, EventType, LoadShedderEvent
from .logging import get_logger
from .config import AdaptiveConcurrencyConfig

logger = get_logger(__name__)


class AdaptiveConcurrencyLimiter:
    """
    Adaptive concurrency limiter using an AIMD algorithm.

    This limiter automatically tunes the allowed concurrency level based on
    recent success rates. It is designed for high-throughput asyncio services
    and integrates with the shared configuration and event systems.

    Key characteristics:
    - AIMD algorithm (TCP-like congestion control)
    - Config-based initialization via AdaptiveConcurrencyConfig
    - Async context manager support for ergonomic usage
    - Explicit acquire/release API for advanced control
    - Emits load-level change events for observability
    - No external dependencies

    Basic usage:

        from aioresilience import AdaptiveConcurrencyLimiter
        from aioresilience.config import AdaptiveConcurrencyConfig

        config = AdaptiveConcurrencyConfig(
            initial_limit=100,
            min_limit=10,
            max_limit=1000,
        )
        limiter = AdaptiveConcurrencyLimiter("api-limiter", config)

        # Recommended: async context manager
        async def handle_request():
            async with limiter:
                return await process_request()

        # Manual acquire/release
        async def handle_request_manual():
            if await limiter.acquire():
                try:
                    result = await process_request()
                    await limiter.release(success=True)
                    return result
                except Exception:
                    await limiter.release(success=False)
                    raise
            else:
                raise RuntimeError("Adaptive limiter at capacity")

    """
    
    def __init__(
        self,
        name: str = "adaptive-concurrency",
        config: Optional[AdaptiveConcurrencyConfig] = None,
    ):
        """
        Initialize adaptive concurrency limiter.

        Args:
            name:
                Name of the limiter instance. Used for metrics and events.
            config:
                AdaptiveConcurrencyConfig instance. If omitted, a default,
                validated configuration is used.

        Example:
            >>> from aioresilience.config import AdaptiveConcurrencyConfig
            >>> cfg = AdaptiveConcurrencyConfig(
            ...     initial_limit=100,
            ...     min_limit=10,
            ...     max_limit=1000,
            ...     success_threshold=0.95,
            ...     failure_threshold=0.80,
            ... )
            >>> limiter = AdaptiveConcurrencyLimiter("api-limiter", cfg)
        """
        self.name = name
        self.config = config or AdaptiveConcurrencyConfig()
        
        # Initialize from config
        self.current_limit = self.config.initial_limit
        self.min_limit = self.config.min_limit
        self.max_limit = self.config.max_limit
        self.increase_rate = self.config.increase_rate
        self.decrease_factor = self.config.decrease_factor
        self.measurement_window = self.config.measurement_window
        self.success_threshold = self.config.success_threshold
        self.failure_threshold = self.config.failure_threshold
        
        # Runtime state
        self.active_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_requests = 0
        
        self._lock = asyncio.Lock()
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=name)
    
    async def acquire(self) -> bool:
        """
        Try to acquire concurrency slot.
        
        Returns:
            True if acquired, False if at limit
        """
        async with self._lock:
            if self.active_count >= self.current_limit:
                return False
            self.active_count += 1
            self.total_requests += 1
            return True
    
    async def release(self, success: bool = True):
        """
        Release concurrency slot and adjust limit.
        
        Args:
            success: Whether request succeeded
        """
        event_to_emit = None
        
        async with self._lock:
            self.active_count = max(0, self.active_count - 1)
            
            if success:
                self.success_count += 1
            else:
                self.failure_count += 1
            
            # Adjust limit every measurement_window requests
            if (self.success_count + self.failure_count) >= self.measurement_window:
                event_to_emit = await self._adjust_limit()
                self.success_count = 0
                self.failure_count = 0
        
        # Emit event outside of lock
        if event_to_emit:
            await self.events.emit(event_to_emit)
    
    async def _adjust_limit(self) -> Optional[LoadShedderEvent]:
        """
        Adjust concurrency limit using AIMD algorithm.
        
        Returns:
            Event to emit (or None if no adjustment made)
        """
        total = self.success_count + self.failure_count
        success_rate = self.success_count / total if total > 0 else 0
        
        if success_rate > self.success_threshold:
            # High success rate: increase limit (additive)
            old_limit = self.current_limit
            self.current_limit = min(
                self.max_limit,
                self.current_limit + self.increase_rate
            )
            if old_limit != self.current_limit:
                logger.info(
                    f"Adaptive limiter '{self.name}': Limit increased {old_limit} → {self.current_limit} "
                    f"(success rate: {success_rate:.2%})"
                )
                
                # Create event to emit outside lock
                return LoadShedderEvent(
                    pattern_type=PatternType.ADAPTIVE_CONCURRENCY,
                    event_type=EventType.LOAD_LEVEL_CHANGE,
                    pattern_name=self.name,
                    active_requests=self.active_count,
                    max_requests=int(self.current_limit),
                    load_level=f"increased:{old_limit}->{self.current_limit}",
                    reason=f"High success rate: {success_rate:.2%}",
                )
        
        elif success_rate < self.failure_threshold:
            # Low success rate: decrease limit (multiplicative)
            old_limit = self.current_limit
            self.current_limit = max(
                self.min_limit,
                int(self.current_limit * self.decrease_factor)
            )
            if old_limit != self.current_limit:
                logger.warning(
                    f"Adaptive limiter '{self.name}': Limit decreased {old_limit} → {self.current_limit} "
                    f"(success rate: {success_rate:.2%})"
                )
                
                # Create event to emit outside lock
                return LoadShedderEvent(
                    pattern_type=PatternType.ADAPTIVE_CONCURRENCY,
                    event_type=EventType.LOAD_LEVEL_CHANGE,
                    pattern_name=self.name,
                    active_requests=self.active_count,
                    max_requests=int(self.current_limit),
                    load_level=f"decreased:{old_limit}->{self.current_limit}",
                    reason=f"Low success rate: {success_rate:.2%}",
                )
        
        return None
    
    async def __aenter__(self):
        """
        Async context manager entry.
        
        Returns:
            Self if acquired, raises if at limit
            
        Example:
            >>> async with limiter:
            ...     result = await process_request()
        """
        acquired = await self.acquire()
        if not acquired:
            raise RuntimeError(f"Adaptive limiter '{self.name}' at capacity ({self.current_limit})")
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Async context manager exit.
        
        Args:
            exc_type: Exception type (if any)
            exc_val: Exception value (if any)
            exc_tb: Exception traceback (if any)
        """
        # Consider request successful if no exception
        success = exc_type is None
        await self.release(success=success)
        return False  # Don't suppress exceptions
    
    def get_stats(self) -> dict:
        """Get limiter statistics"""
        return {
            "current_limit": self.current_limit,
            "active_count": self.active_count,
            "total_requests": self.total_requests,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "utilization": (self.active_count / self.current_limit) * 100 if self.current_limit > 0 else 0,
        }
