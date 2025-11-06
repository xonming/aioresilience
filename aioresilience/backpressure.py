"""
Backpressure Management

Manages async processing backpressure with water marks and event-based signaling.

Dependencies: None (pure Python async)
"""

import asyncio
from typing import Optional, Callable, Any
from functools import wraps
from typing import Optional, Callable, Any

from .events import EventEmitter, PatternType, EventType, LoadShedderEvent
from .logging import get_logger

logger = get_logger(__name__)


class BackpressureManager:
    """
    Backpressure management for async processing pipelines.
    
    Signals upstream to slow down when overloaded using water marks.
    
    Features:
    - High/low water mark system
    - Event-based flow control
    - Timeout support
    - No external dependencies
    
    Example:
        backpressure = BackpressureManager(
            max_pending=1000,
            high_water_mark=800,
            low_water_mark=200
        )
        
        if await backpressure.acquire(timeout=5.0):
            try:
                await process_item()
            finally:
                await backpressure.release()
    """
    
    def __init__(
        self,
        max_pending: int = 1000,
        high_water_mark: int = 800,
        low_water_mark: int = 200,
    ):
        """
        Initialize backpressure manager.
        
        Args:
            max_pending: Maximum pending items (hard limit)
            high_water_mark: Start applying backpressure
            low_water_mark: Stop applying backpressure
        """
        self.max_pending = max_pending
        self.high_water_mark = high_water_mark
        self.low_water_mark = low_water_mark
        
        self.pending_count = 0
        self.backpressure_active = False
        self.total_rejected = 0
        
        self._lock = asyncio.Lock()
        self._resume_event = asyncio.Event()
        self._resume_event.set()  # Initially not blocked
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=f"backpressure-{id(self)}")
    
    @property
    def is_overloaded(self) -> bool:
        """Check if system is overloaded"""
        return self.pending_count >= self.max_pending
    
    @property
    def should_apply_backpressure(self) -> bool:
        """Check if backpressure should be applied"""
        return self.pending_count >= self.high_water_mark
    
    async def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire slot for processing.
        
        Args:
            timeout: Wait timeout in seconds (None = wait forever)
        
        Returns:
            True if acquired, False if rejected
        """
        # Hard limit check
        if self.pending_count >= self.max_pending:
            self.total_rejected += 1
            logger.warning(f"Backpressure: Max pending reached ({self.pending_count}/{self.max_pending})")
            return False
        
        # Wait if backpressure is active
        if self.backpressure_active:
            try:
                await asyncio.wait_for(self._resume_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                self.total_rejected += 1
                logger.warning("Backpressure: Timeout waiting for capacity")
                return False
        
        async with self._lock:
            if self.pending_count >= self.max_pending:
                return False
            
            self.pending_count += 1
            
            # Activate backpressure if needed
            if self.pending_count >= self.high_water_mark and not self.backpressure_active:
                self.backpressure_active = True
                self._resume_event.clear()
                logger.warning(f"Backpressure ACTIVE: {self.pending_count}/{self.high_water_mark}")
                
                # Emit backpressure threshold exceeded event
                await self.events.emit(LoadShedderEvent(
                    pattern_type=PatternType.BACKPRESSURE,
                    event_type=EventType.THRESHOLD_EXCEEDED,
                    pattern_name=self.events.pattern_name,
                    active_requests=self.pending_count,
                    max_requests=self.max_pending,
                    load_level="high",
                    reason=f"High water mark exceeded: {self.pending_count}/{self.high_water_mark}",
                ))
        
        return True
    
    async def release(self):
        """Release processing slot"""
        async with self._lock:
            self.pending_count = max(0, self.pending_count - 1)
            
            # Deactivate backpressure if needed
            if self.pending_count <= self.low_water_mark and self.backpressure_active:
                self.backpressure_active = False
                self._resume_event.set()
                logger.info(f"Backpressure INACTIVE: {self.pending_count}/{self.low_water_mark}")
                
                # Emit backpressure load level change event
                await self.events.emit(LoadShedderEvent(
                    pattern_type=PatternType.BACKPRESSURE,
                    event_type=EventType.LOAD_LEVEL_CHANGE,
                    pattern_name=self.events.pattern_name,
                    active_requests=self.pending_count,
                    max_requests=self.max_pending,
                    load_level="normal",
                    reason=f"Low water mark reached: {self.pending_count}/{self.low_water_mark}",
                ))
    
    def get_stats(self) -> dict:
        """Get backpressure statistics"""
        return {
            "pending_count": self.pending_count,
            "max_pending": self.max_pending,
            "backpressure_active": self.backpressure_active,
            "total_rejected": self.total_rejected,
            "utilization": (self.pending_count / self.max_pending) * 100,
        }


# Decorator for backpressure
def with_backpressure(backpressure: BackpressureManager, timeout: Optional[float] = None):
    """
    Decorator to add backpressure to a function.
    
    Example:
        backpressure = BackpressureManager()
        
        @with_backpressure(backpressure, timeout=5.0)
        async def process_item(item):
            # Your code
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not await backpressure.acquire(timeout):
                raise RuntimeError("Backpressure: System overloaded")
            
            try:
                return await func(*args, **kwargs)
            finally:
                await backpressure.release()
        
        return wrapper
    return decorator
