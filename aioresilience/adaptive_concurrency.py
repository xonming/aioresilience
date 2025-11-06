"""
Adaptive Concurrency Limiter

AIMD (Additive Increase Multiplicative Decrease) algorithm for auto-adjusting concurrency.

Dependencies: None (pure Python async)
"""

import asyncio
from dataclasses import dataclass
from typing import Optional

from .events import EventEmitter, PatternType, EventType, LoadShedderEvent
from .logging import get_logger

logger = get_logger(__name__)


class AdaptiveConcurrencyLimiter:
    """
    Adaptive concurrency limiter using AIMD algorithm.
    
    Automatically adjusts concurrency limits based on success rate.
    
    Features:
    - AIMD algorithm (TCP-like congestion control)
    - Success rate measurement
    - Configurable limits and adjustment rates
    - No external dependencies
    
    Example:
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            min_limit=10,
            max_limit=1000
        )
        
        if await limiter.acquire():
            try:
                result = await process_request()
                await limiter.release(success=True)
            except Exception:
                await limiter.release(success=False)
    """
    
    def __init__(
        self,
        initial_limit: int = 100,
        min_limit: int = 10,
        max_limit: int = 1000,
        increase_rate: float = 1.0,
        decrease_factor: float = 0.9,
        measurement_window: int = 100,
    ):
        """
        Initialize adaptive limiter.
        
        Args:
            initial_limit: Starting concurrency limit
            min_limit: Minimum concurrency limit
            max_limit: Maximum concurrency limit
            increase_rate: Additive increase per success window
            decrease_factor: Multiplicative decrease on failure
            measurement_window: Number of requests to measure success rate
        """
        self.current_limit = initial_limit
        self.min_limit = min_limit
        self.max_limit = max_limit
        self.increase_rate = increase_rate
        self.decrease_factor = decrease_factor
        self.measurement_window = measurement_window
        
        self.active_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.total_requests = 0
        
        self._lock = asyncio.Lock()
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=f"adaptive-concurrency-{id(self)}")
    
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
        async with self._lock:
            self.active_count = max(0, self.active_count - 1)
            
            if success:
                self.success_count += 1
            else:
                self.failure_count += 1
            
            # Adjust limit every measurement_window requests
            if (self.success_count + self.failure_count) >= self.measurement_window:
                await self._adjust_limit()
                self.success_count = 0
                self.failure_count = 0
    
    async def _adjust_limit(self):
        """Adjust concurrency limit using AIMD algorithm"""
        total = self.success_count + self.failure_count
        success_rate = self.success_count / total if total > 0 else 0
        
        if success_rate > 0.95:
            # High success rate: increase limit (additive)
            old_limit = self.current_limit
            self.current_limit = min(
                self.max_limit,
                self.current_limit + self.increase_rate
            )
            if old_limit != self.current_limit:
                logger.info(f"Concurrency limit increased: {old_limit} → {self.current_limit}")
                
                # Emit limit change event
                await self.events.emit(LoadShedderEvent(
                    pattern_type=PatternType.ADAPTIVE_CONCURRENCY,
                    event_type=EventType.LOAD_LEVEL_CHANGE,
                    pattern_name=self.events.pattern_name,
                    active_requests=self.active_count,
                    max_requests=int(self.current_limit),
                    load_level=f"increased:{old_limit}->{self.current_limit}",
                    reason=f"High success rate: {success_rate:.2%}",
                ))
        
        elif success_rate < 0.80:
            # Low success rate: decrease limit (multiplicative)
            old_limit = self.current_limit
            self.current_limit = max(
                self.min_limit,
                int(self.current_limit * self.decrease_factor)
            )
            if old_limit != self.current_limit:
                logger.warning(f"Concurrency limit decreased: {old_limit} → {self.current_limit}")
                
                # Emit limit change event
                await self.events.emit(LoadShedderEvent(
                    pattern_type=PatternType.ADAPTIVE_CONCURRENCY,
                    event_type=EventType.LOAD_LEVEL_CHANGE,
                    pattern_name=self.events.pattern_name,
                    active_requests=self.active_count,
                    max_requests=int(self.current_limit),
                    load_level=f"decreased:{old_limit}->{self.current_limit}",
                    reason=f"Low success rate: {success_rate:.2%}",
                ))
    
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
