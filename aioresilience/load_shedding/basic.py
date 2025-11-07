"""
Basic Load Shedder

Request-count-based load shedding without system metrics.
No external dependencies.

Dependencies: None (pure Python)
"""

import time
import asyncio
from typing import Optional, Callable, Any, Type
from dataclasses import dataclass
from enum import IntEnum
from functools import wraps

from ..events import EventEmitter, PatternType, EventType, LoadShedderEvent
from ..logging import get_logger
from ..config import LoadSheddingConfig
from ..exceptions import (
    LoadSheddingError,
    LoadSheddingReason,
    ExceptionHandler,
    ExceptionContext,
    ExceptionConfig,
)

logger = get_logger(__name__)


class LoadLevel(IntEnum):
    """Load levels based on request count (IntEnum for performance)"""
    NORMAL = 0      # Normal load (most common)
    ELEVATED = 1    # Elevated load
    HIGH = 2        # High load  
    CRITICAL = 3    # Critical load


@dataclass
class LoadMetrics:
    """Load metrics"""
    active_requests: int
    queue_depth: int
    max_requests: int
    max_queue_depth: int
    timestamp: float
    
    @property
    def load_level(self) -> LoadLevel:
        """Determine current load level based on request count"""
        utilization = (self.active_requests / self.max_requests) * 100
        
        if utilization > 90:
            return LoadLevel.CRITICAL
        elif utilization > 75:
            return LoadLevel.HIGH
        elif utilization > 60:
            return LoadLevel.ELEVATED
        else:
            return LoadLevel.NORMAL


class BasicLoadShedder:
    """
    Basic load shedding based on request count and queue depth.
    
    No system metrics (CPU/memory) monitoring.
    Suitable for applications where request count limits are sufficient.
    
    Features:
    - Request count limiting
    - Queue depth management
    - Priority-based request handling
    - No external dependencies
    
    Example:
        load_shedder = BasicLoadShedder(
            max_requests=1000,
            max_queue_depth=500
        )
        
        if await load_shedder.acquire():
            try:
                await process_request()
            finally:
                await load_shedder.release()
    """
    
    def __init__(
        self,
        config: Optional[LoadSheddingConfig] = None,
        exceptions: Optional[ExceptionConfig] = None,
    ):
        """
        Initialize basic load shedder.
        
        Args:
            config: Optional LoadSheddingConfig for pattern settings
            exceptions: Optional ExceptionConfig for exception handling
        """
        # Initialize config with defaults
        if config is None:
            config = LoadSheddingConfig()
        
        self.max_requests = config.max_requests
        self.max_queue_depth = config.max_queue_depth
        
        self.active_requests = 0
        self.queue_depth = 0
        self.total_shed = 0
        
        self._lock = asyncio.Lock()
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=f"load-shedder-{id(self)}")
        
        # Initialize exception handling
        if exceptions is None:
            exceptions = ExceptionConfig()
        
        self._exception_handler = ExceptionHandler(
            pattern_name=f"load-shedder-{id(self)}",
            pattern_type="load_shedding",
            handled_exceptions=exceptions.handled_exceptions or (Exception,),
            exception_type=exceptions.exception_type or LoadSheddingError,
            exception_transformer=exceptions.exception_transformer,
            on_exception=exceptions.on_exception,
        )
    
    def _get_load_metrics(self) -> LoadMetrics:
        """Get current load metrics"""
        return LoadMetrics(
            active_requests=self.active_requests,
            queue_depth=self.queue_depth,
            max_requests=self.max_requests,
            max_queue_depth=self.max_queue_depth,
            timestamp=time.time()
        )
    
    def should_shed_load(self) -> tuple[bool, str]:
        """
        Determine if load should be shed.
        
        Returns:
            (should_shed, reason)
        """
        # Check request limit
        if self.active_requests >= self.max_requests:
            return True, f"Max concurrent requests reached ({self.active_requests}/{self.max_requests})"
        
        # Check queue depth
        if self.queue_depth >= self.max_queue_depth:
            return True, f"Queue depth exceeded ({self.queue_depth}/{self.max_queue_depth})"
        
        return False, ""
    
    async def acquire(self, priority: str = "normal") -> bool:
        """
        Acquire permission to process request.
        
        Args:
            priority: Request priority (high/normal/low)
        
        Returns:
            True if request should be processed, False if shed
        """
        async with self._lock:
            should_shed, reason = self.should_shed_load()
            
            # High priority requests bypass some checks
            if priority == "high" and self.active_requests < self.max_requests:
                should_shed = False
            
            if should_shed:
                self.total_shed += 1
                logger.warning(f"Load shed: {reason} (total shed: {self.total_shed})")
                
                # Emit request shed event
                metrics = self._get_load_metrics()
                await self.events.emit(LoadShedderEvent(
                    pattern_type=PatternType.LOAD_SHEDDER,
                    event_type=EventType.REQUEST_SHED,
                    pattern_name=self.events.pattern_name,
                    active_requests=self.active_requests,
                    max_requests=self.max_requests,
                    load_level=metrics.load_level.value,
                    reason=reason,
                ))
                
                return False
            
            self.active_requests += 1
            
            # Emit request accepted event
            metrics = self._get_load_metrics()
            await self.events.emit(LoadShedderEvent(
                pattern_type=PatternType.LOAD_SHEDDER,
                event_type=EventType.REQUEST_ACCEPTED,
                pattern_name=self.events.pattern_name,
                active_requests=self.active_requests,
                max_requests=self.max_requests,
                load_level=metrics.load_level.value,
            ))
            return True
    
    async def release(self):
        """Release request slot"""
        async with self._lock:
            self.active_requests = max(0, self.active_requests - 1)
    
    def get_stats(self) -> dict:
        """Get load shedder statistics"""
        metrics = self._get_load_metrics()
        return {
            "active_requests": self.active_requests,
            "queue_depth": self.queue_depth,
            "total_shed": self.total_shed,
            "load_level": metrics.load_level.value,
            "max_requests": self.max_requests,
            "max_queue_depth": self.max_queue_depth,
            "utilization": (self.active_requests / self.max_requests) * 100,
            "type": "basic",
        }
    
    async def _raise_load_shedding_error(self, reason: LoadSheddingReason):
        """Raise load shedding error using configured exception handler"""
        _, exc = await self._exception_handler.handle_exception(
            reason=reason,
            original_exc=None,
            message="Service overloaded - load shed",
            active_requests=self.active_requests,
            max_requests=self.max_requests,
            queue_depth=self.queue_depth,
        )
        raise exc


# Decorator for load shedding
def with_load_shedding(load_shedder: 'BasicLoadShedder', priority: str = "normal"):
    """
    Decorator to add load shedding to a function.
    
    Raises LoadSheddingError if load should be shed.
    For web framework integration, catch this and return appropriate HTTP response.
    
    Example:
        load_shedder = BasicLoadShedder()
        
        @with_load_shedding(load_shedder, priority="high")
        async def process_message(msg):
            # Your code
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            if not await load_shedder.acquire(priority):
                await load_shedder._raise_load_shedding_error(LoadSheddingReason.MAX_LOAD_EXCEEDED)
            
            try:
                return await func(*args, **kwargs)
            finally:
                await load_shedder.release()
        
        return wrapper
    return decorator
