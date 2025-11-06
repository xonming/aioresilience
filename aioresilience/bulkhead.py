"""
Bulkhead Pattern Module

Provides resource isolation through bulkheading to prevent cascading failures.
Limits concurrent access to specific resources or operations.
"""

import asyncio
import functools
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .events import EventEmitter, PatternType, EventType, BulkheadEvent
from .logging import get_logger

logger = get_logger(__name__)


class BulkheadFullError(Exception):
    """Raised when bulkhead is at capacity and cannot accept more requests"""
    pass


@dataclass
class BulkheadMetrics:
    """Metrics for bulkhead operations"""
    total_requests: int = 0
    successful_requests: int = 0
    rejected_requests: int = 0
    current_active: int = 0
    peak_active: int = 0
    total_wait_time: float = 0.0
    average_wait_time: float = 0.0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary"""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "rejected_requests": self.rejected_requests,
            "current_active": self.current_active,
            "peak_active": self.peak_active,
            "total_wait_time": self.total_wait_time,
            "average_wait_time": self.average_wait_time,
            "rejection_rate": (
                self.rejected_requests / self.total_requests
                if self.total_requests > 0 else 0.0
            ),
            "utilization": self.current_active,
        }


class Bulkhead:
    """
    Bulkhead pattern for resource isolation.
    
    Limits concurrent execution to prevent resource exhaustion and
    isolate failures to specific resource pools.
    
    Args:
        max_concurrent: Maximum number of concurrent executions
        max_waiting: Maximum number of requests waiting in queue (0 = reject immediately)
        timeout: Maximum time to wait for a slot (None = wait indefinitely)
        name: Optional name for the bulkhead
    """
    
    def __init__(
        self,
        max_concurrent: int,
        max_waiting: int = 0,
        timeout: Optional[float] = None,
        name: str = "bulkhead",
    ):
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be at least 1")
        if max_waiting < 0:
            raise ValueError("max_waiting must be non-negative")
        if timeout is not None and timeout <= 0:
            raise ValueError("timeout must be positive or None")
        
        self.max_concurrent = max_concurrent
        self.max_waiting = max_waiting
        self.timeout = timeout
        self.name = name
        
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._metrics = BulkheadMetrics()
        self._lock = asyncio.Lock()
        self._waiting_count = 0
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=name)
    
    async def _try_acquire(self) -> bool:
        """Try to acquire a slot, respecting waiting limit"""
        # Try to acquire immediately (fast path - no lock needed)
        if not self._semaphore.locked():
            await self._semaphore.acquire()
            # Update metrics atomically
            async with self._lock:
                self._metrics.total_requests += 1
            return True
        
        # Slow path: Semaphore at capacity, check if we can wait
        async with self._lock:
            if self._waiting_count >= self.max_waiting:
                return False
            self._waiting_count += 1
            self._metrics.total_requests += 1  # Batch with waiting_count update
        
        try:
            if self.timeout:
                await asyncio.wait_for(
                    self._semaphore.acquire(),
                    timeout=self.timeout
                )
            else:
                await self._semaphore.acquire()
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            async with self._lock:
                self._waiting_count -= 1
    
    async def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function within the bulkhead.
        
        Args:
            func: Async or sync callable to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func
        
        Returns:
            Result of function execution
        
        Raises:
            BulkheadFullError: If bulkhead is at capacity
        """
        start_wait = time.perf_counter()  # Faster than time.time()
        
        # Try to acquire a slot (metrics updated inside _try_acquire)
        acquired = await self._try_acquire()
        
        if not acquired:
            async with self._lock:
                self._metrics.total_requests += 1
                self._metrics.rejected_requests += 1
            
            # Emit bulkhead full event
            await self.events.emit(BulkheadEvent(
                pattern_type=PatternType.BULKHEAD,
                event_type=EventType.BULKHEAD_FULL,
                pattern_name=self.name,
                active_count=self._metrics.current_active,
                waiting_count=self._waiting_count,
                max_concurrent=self.max_concurrent,
                max_waiting=self.max_waiting,
            ))
            
            logger.warning(
                f"Bulkhead '{self.name}' is full "
                f"(max_concurrent: {self.max_concurrent}, "
                f"max_waiting: {self.max_waiting})"
            )
            raise BulkheadFullError(
                f"Bulkhead '{self.name}' is at capacity"
            )
        
        wait_time = time.perf_counter() - start_wait
        
        # Check if function is async (cache for fast path)
        is_coroutine = asyncio.iscoroutinefunction(func)
        
        try:
            # Batch all metrics updates into single lock acquisition
            async with self._lock:
                self._metrics.current_active += 1
                self._metrics.peak_active = max(
                    self._metrics.peak_active,
                    self._metrics.current_active
                )
                self._metrics.total_wait_time += wait_time
                if self._metrics.total_requests > 0:
                    self._metrics.average_wait_time = (
                        self._metrics.total_wait_time / self._metrics.total_requests
                    )
                active_count_snapshot = self._metrics.current_active
            
            # Emit slot acquired event (outside lock)
            await self.events.emit(BulkheadEvent(
                pattern_type=PatternType.BULKHEAD,
                event_type=EventType.SLOT_ACQUIRED,
                pattern_name=self.name,
                active_count=active_count_snapshot,
                waiting_count=self._waiting_count,
                max_concurrent=self.max_concurrent,
                max_waiting=self.max_waiting,
            ))
            
            # Execute the function
            if is_coroutine:
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.to_thread(func, *args, **kwargs)
            
            # Batch success metric with release
            async with self._lock:
                self._metrics.successful_requests += 1
                self._metrics.current_active -= 1
                active_count_after = self._metrics.current_active
            
            self._semaphore.release()
            
            # Emit slot released event (outside lock, in try/except)
            try:
                await self.events.emit(BulkheadEvent(
                    pattern_type=PatternType.BULKHEAD,
                    event_type=EventType.SLOT_RELEASED,
                    pattern_name=self.name,
                    active_count=active_count_after,
                    waiting_count=self._waiting_count,
                    max_concurrent=self.max_concurrent,
                    max_waiting=self.max_waiting,
                ))
            except Exception as e:
                logger.warning(f"Failed to emit slot released event: {e}")
            
            return result
            
        except Exception:
            # On exception, still need to release resources
            async with self._lock:
                self._metrics.current_active -= 1
            self._semaphore.release()
            raise
    
    async def __aenter__(self):
        """Async context manager entry"""
        # _try_acquire now handles total_requests increment
        acquired = await self._try_acquire()
        if not acquired:
            async with self._lock:
                self._metrics.rejected_requests += 1
            raise BulkheadFullError(
                f"Bulkhead '{self.name}' is at capacity"
            )
        
        async with self._lock:
            self._metrics.current_active += 1
            self._metrics.peak_active = max(
                self._metrics.peak_active,
                self._metrics.current_active
            )
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        async with self._lock:
            self._metrics.current_active -= 1
            if exc_type is None:
                self._metrics.successful_requests += 1
        self._semaphore.release()
        return False
    
    def get_metrics(self) -> dict[str, Any]:
        """Get bulkhead metrics"""
        return self._metrics.to_dict()
    
    def reset_metrics(self) -> None:
        """Reset metrics counters"""
        current_active = self._metrics.current_active
        peak_active = self._metrics.peak_active
        self._metrics = BulkheadMetrics()
        self._metrics.current_active = current_active
        self._metrics.peak_active = peak_active
    
    def is_full(self) -> bool:
        """Check if bulkhead is at capacity"""
        return self._semaphore.locked()
    
    def available_slots(self) -> int:
        """Get number of available execution slots"""
        # Note: _value is implementation detail but commonly available
        return getattr(self._semaphore, '_value', 0)


def bulkhead(
    max_concurrent: int,
    max_waiting: int = 0,
    timeout: Optional[float] = None,
    name: Optional[str] = None,
):
    """
    Decorator to protect async functions with bulkhead pattern.
    
    Example:
        @bulkhead(max_concurrent=5, max_waiting=10, timeout=5.0)
        async def process_data(data):
            # This function will only run max 5 concurrent instances
            # with up to 10 waiting in queue
            return await heavy_processing(data)
    """
    def decorator(func: Callable) -> Callable:
        bulkhead_name = name or f"bulkhead_{func.__name__}"
        bulkhead_instance = Bulkhead(
            max_concurrent=max_concurrent,
            max_waiting=max_waiting,
            timeout=timeout,
            name=bulkhead_name,
        )
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await bulkhead_instance.execute(func, *args, **kwargs)
        
        # Attach bulkhead for metrics access
        wrapper.bulkhead = bulkhead_instance
        
        return wrapper
    
    return decorator


class BulkheadRegistry:
    """
    Registry for managing multiple named bulkheads.
    
    Useful for isolating different resource pools (database, external API, etc.)
    """
    
    def __init__(self):
        self._bulkheads: dict[str, Bulkhead] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_create(
        self,
        name: str,
        max_concurrent: int,
        max_waiting: int = 0,
        timeout: Optional[float] = None,
    ) -> Bulkhead:
        """Get existing bulkhead or create a new one"""
        async with self._lock:
            if name not in self._bulkheads:
                self._bulkheads[name] = Bulkhead(
                    max_concurrent=max_concurrent,
                    max_waiting=max_waiting,
                    timeout=timeout,
                    name=name,
                )
            return self._bulkheads[name]
    
    def get(self, name: str) -> Optional[Bulkhead]:
        """Get bulkhead by name"""
        return self._bulkheads.get(name)
    
    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all bulkheads"""
        return {
            name: bulkhead.get_metrics()
            for name, bulkhead in self._bulkheads.items()
        }
    
    def reset_all_metrics(self) -> None:
        """Reset metrics for all bulkheads"""
        for bulkhead in self._bulkheads.values():
            bulkhead.reset_metrics()


# Global registry instance
_registry = BulkheadRegistry()


async def get_bulkhead(
    name: str,
    max_concurrent: int,
    max_waiting: int = 0,
    timeout: Optional[float] = None,
) -> Bulkhead:
    """Get or create a named bulkhead from global registry"""
    return await _registry.get_or_create(name, max_concurrent, max_waiting, timeout)


def get_all_bulkhead_metrics() -> dict[str, dict[str, Any]]:
    """Get metrics for all registered bulkheads"""
    return _registry.get_all_metrics()
