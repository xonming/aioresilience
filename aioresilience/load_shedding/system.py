"""
System-Aware Load Shedder

Load shedding with CPU and memory monitoring using psutil.

Dependencies:
- psutil (required) - pip install psutil

Install:
    pip install aioresilience[system]
"""

import time
import asyncio
from typing import Optional
from dataclasses import dataclass
from enum import Enum
import logging

try:
    import psutil
    _has_psutil = True
except ImportError:
    _has_psutil = False
    psutil = None

from .basic import BasicLoadShedder, LoadLevel

logger = logging.getLogger(__name__)


@dataclass
class SystemLoadMetrics:
    """System load metrics with CPU/memory"""
    cpu_percent: float
    memory_percent: float
    active_requests: int
    queue_depth: int
    max_requests: int
    max_queue_depth: int
    timestamp: float
    
    @property
    def load_level(self) -> LoadLevel:
        """Determine current load level based on system metrics"""
        if self.cpu_percent > 90 or self.memory_percent > 90:
            return LoadLevel.CRITICAL
        elif self.cpu_percent > 75 or self.memory_percent > 80:
            return LoadLevel.HIGH
        elif self.cpu_percent > 60 or self.memory_percent > 70:
            return LoadLevel.ELEVATED
        else:
            return LoadLevel.NORMAL


class SystemLoadShedder(BasicLoadShedder):
    """
    System-aware load shedder with CPU and memory monitoring.
    
    Extends BasicLoadShedder with system metrics.
    Requires psutil for CPU/memory monitoring.
    
    Features:
    - Request count limiting
    - CPU threshold monitoring
    - Memory threshold monitoring
    - Priority-based request handling
    
    Example:
        load_shedder = SystemLoadShedder(
            max_requests=1000,
            cpu_threshold=85.0,
            memory_threshold=85.0
        )
        
        if await load_shedder.acquire():
            try:
                await process_request()
            finally:
                await load_shedder.release()
    """
    
    def __init__(
        self,
        max_requests: int = 1000,
        max_queue_depth: int = 500,
        cpu_threshold: float = 85.0,
        memory_threshold: float = 85.0,
        check_interval: float = 1.0,
    ):
        """
        Initialize system-aware load shedder.
        
        Args:
            max_requests: Maximum concurrent requests
            max_queue_depth: Maximum queue depth
            cpu_threshold: CPU threshold for shedding (%)
            memory_threshold: Memory threshold for shedding (%)
            check_interval: How often to check system metrics (seconds)
        """
        if not _has_psutil:
            raise ImportError(
                "SystemLoadShedder requires 'psutil' package for system monitoring. "
                "Install it with: pip install psutil"
            )
        
        super().__init__(max_requests, max_queue_depth)
        
        self._psutil = psutil
        self.cpu_threshold = cpu_threshold
        self.memory_threshold = memory_threshold
        self.check_interval = check_interval
        
        self.last_check = 0.0
        self.cached_metrics: Optional[SystemLoadMetrics] = None
    
    def _get_system_metrics(self) -> SystemLoadMetrics:
        """Get current system metrics"""
        now = time.time()
        
        # Cache metrics to avoid excessive system calls
        if self.cached_metrics and (now - self.last_check) < self.check_interval:
            return self.cached_metrics
        
        cpu_percent = self._psutil.cpu_percent(interval=0.1)
        memory_percent = self._psutil.virtual_memory().percent
        
        metrics = SystemLoadMetrics(
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            active_requests=self.active_requests,
            queue_depth=self.queue_depth,
            max_requests=self.max_requests,
            max_queue_depth=self.max_queue_depth,
            timestamp=now
        )
        
        self.cached_metrics = metrics
        self.last_check = now
        
        return metrics
    
    def should_shed_load(self) -> tuple[bool, str]:
        """
        Determine if load should be shed based on system metrics.
        
        Returns:
            (should_shed, reason)
        """
        # Check base conditions first
        should_shed, reason = super().should_shed_load()
        if should_shed:
            return should_shed, reason
        
        # Check system metrics
        metrics = self._get_system_metrics()
        
        if metrics.cpu_percent > self.cpu_threshold:
            return True, f"CPU threshold exceeded ({metrics.cpu_percent:.1f}% > {self.cpu_threshold}%)"
        
        if metrics.memory_percent > self.memory_threshold:
            return True, f"Memory threshold exceeded ({metrics.memory_percent:.1f}% > {self.memory_threshold}%)"
        
        return False, ""
    
    async def acquire(self, priority: str = "normal") -> bool:
        """
        Acquire permission to process request with system metrics check.
        
        Args:
            priority: Request priority (high/normal/low)
        
        Returns:
            True if request should be processed, False if shed
        """
        async with self._lock:
            should_shed, reason = self.should_shed_load()
            
            # High priority requests bypass some checks, but not CRITICAL load
            if priority == "high" and not (
                self.active_requests >= self.max_requests or
                self._get_system_metrics().load_level == LoadLevel.CRITICAL
            ):
                should_shed = False
            
            if should_shed:
                self.total_shed += 1
                logger.warning(f"Load shed: {reason} (total shed: {self.total_shed})")
                return False
            
            self.active_requests += 1
            return True
    
    def get_stats(self) -> dict:
        """Get load shedder statistics with system metrics"""
        metrics = self._get_system_metrics()
        base_stats = super().get_stats()
        base_stats.update({
            "cpu_percent": metrics.cpu_percent,
            "memory_percent": metrics.memory_percent,
            "load_level": metrics.load_level.value,
            "type": "system",
        })
        return base_stats
