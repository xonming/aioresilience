"""
Backpressure Management

Manages async processing backpressure with water marks and event-based signaling.

Dependencies: None (pure Python async)
"""

import asyncio
from typing import Optional, Callable, Any, Type
from functools import wraps

from .events import EventEmitter, PatternType, EventType, LoadShedderEvent
from .logging import get_logger
from .config import BackpressureConfig
from .exceptions import (
    BackpressureError,
    BackpressureReason,
    ExceptionHandler,
    ExceptionContext,
    ExceptionConfig,
)

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
        config: Optional[BackpressureConfig] = None,
        exceptions: Optional[ExceptionConfig] = None,
    ):
        """
        Initialize backpressure manager.
        
        Args:
            config: Optional BackpressureConfig for pattern settings
            exceptions: Optional ExceptionConfig for exception handling
        """
        # Initialize config with defaults
        if config is None:
            config = BackpressureConfig()
        
        self.max_pending = config.max_pending
        self.high_water_mark = config.high_water_mark
        self.low_water_mark = config.low_water_mark
        
        self.pending_count = 0
        self.backpressure_active = False
        self.total_rejected = 0
        
        self._lock = asyncio.Lock()
        self._resume_event = asyncio.Event()
        self._resume_event.set()  # Initially not blocked
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=f"backpressure-{id(self)}")
        
        # Initialize exception handling
        if exceptions is None:
            exceptions = ExceptionConfig()
        
        self._exception_handler = ExceptionHandler(
            pattern_name=f"backpressure-{id(self)}",
            pattern_type="backpressure",
            handled_exceptions=exceptions.handled_exceptions or (Exception,),
            exception_type=exceptions.exception_type or BackpressureError,
            exception_transformer=exceptions.exception_transformer,
            on_exception=exceptions.on_exception,
        )
    
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
        Acquire slot for processing with adaptive backpressure.
        
        Behavior:
        - Below high_water_mark: acquire immediately
        - At max_pending: reject immediately
        - Between high and max with backpressure: wait for low_water_mark
        
        Args:
            timeout: Wait timeout in seconds (None = use default 5s to prevent deadlock)
        
        Returns:
            True if acquired, False if rejected
        """
        # Use default timeout to prevent infinite waits
        effective_timeout = timeout if timeout is not None else 5.0
        
        # Fast path: check if we can acquire immediately
        async with self._lock:
            # Hard reject if at max capacity
            if self.pending_count >= self.max_pending:
                self.total_rejected += 1
                logger.warning(f"Backpressure: Max pending reached ({self.pending_count}/{self.max_pending})")
                return False
            
            # Fast path: below high water mark, acquire immediately
            if self.pending_count < self.high_water_mark:
                self.pending_count += 1
                
                # Check if we just crossed the high water mark
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
        
        # Between high_water_mark and max_pending: wait if backpressure is active
        # This enforces flow control - producers must wait for consumers to drain
        if self.backpressure_active:
            logger.info(f"Backpressure active, waiting for low water mark... (pending={self.pending_count}, timeout={effective_timeout})")
            try:
                # Wait for backpressure to deactivate (consumers drain to low_water_mark)
                await asyncio.wait_for(self._resume_event.wait(), timeout=effective_timeout)
                logger.info(f"Backpressure deactivated, retrying acquire")
            except asyncio.TimeoutError:
                self.total_rejected += 1
                logger.warning(f"Backpressure timeout after {effective_timeout}s, rejecting")
                return False
        
        # After waiting (or if no backpressure), acquire with lock
        async with self._lock:
            # Recheck capacity (might have changed during wait)
            if self.pending_count >= self.max_pending:
                self.total_rejected += 1
                return False
            
            self.pending_count += 1
            
            # Activate backpressure if we just crossed high water mark
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
    
    async def _raise_backpressure_error(self, reason: BackpressureReason):
        """Raise backpressure error using configured exception handler"""
        _, exc = await self._exception_handler.handle_exception(
            reason=reason,
            original_exc=None,
            message="Backpressure: System overloaded",
            pending_count=self.pending_count,
            max_pending=self.max_pending,
        )
        raise exc
    
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
                await backpressure._raise_backpressure_error(BackpressureReason.SYSTEM_OVERLOADED)
            
            try:
                return await func(*args, **kwargs)
            finally:
                await backpressure.release()
        
        return wrapper
    return decorator
