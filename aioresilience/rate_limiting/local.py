"""
Local (In-Memory) Rate Limiter

Uses aiolimiter for async rate limiting.
No external service dependencies (Redis, etc).

Dependencies:
- aiolimiter (required)
"""

import asyncio
import time
from typing import Dict, Optional
from collections import OrderedDict
from aiolimiter import AsyncLimiter
import asyncio

from ..events import EventEmitter, PatternType, EventType, RateLimitEvent
from ..logging import get_logger

logger = get_logger(__name__)


class LocalRateLimiter:
    """
    In-memory rate limiter using aiolimiter.
    
    Suitable for single-instance applications or rate limiting
    that doesn't need to be shared across multiple instances.
    
    Features:
    - Async-first design
    - Leaky bucket algorithm
    - Per-key rate limits
    - No external dependencies
    
    Example:
        rate_limiter = LocalRateLimiter(name="api")
        
        # Check rate limit
        if await rate_limiter.check_rate_limit("user_123", "100/minute"):
            # Process request
        else:
            raise Exception("Rate limit exceeded")
    """
    
    def __init__(self, name: str = "default", max_limiters: int = 10000):
        """
        Initialize local rate limiter.
        
        Args:
            name: Name for this rate limiter (for logging and identification)
            max_limiters: Maximum number of limiters to cache (LRU eviction)
        """
        self.name = name
        self.max_limiters = max_limiters
        self.limiters: OrderedDict[str, AsyncLimiter] = OrderedDict()
        self.logger = logger
        self._lock = asyncio.Lock()
        
        # Event emitter for monitoring
        self.events = EventEmitter(pattern_name=name)
    
    async def get_limiter(self, key: str, rate: str) -> AsyncLimiter:
        """
        Get or create a rate limiter for the given key and rate.
        Uses LRU eviction to prevent unbounded memory growth.
        
        Args:
            key: Unique identifier for the rate limit (e.g., user ID, IP)
            rate: Rate limit string (e.g., "100/minute", "10/second")
            
        Returns:
            AsyncLimiter instance
        """
        limiter_key = f"{key}:{rate}"
        
        # Fast path: check if limiter exists (lock-free read)
        if limiter_key in self.limiters:
            async with self._lock:
                # Double-check inside lock and move to end
                if limiter_key in self.limiters:
                    self.limiters.move_to_end(limiter_key)
                    return self.limiters[limiter_key]
        
        # Slow path: need to create limiter
        async with self._lock:
            # Check again in case another coroutine created it
            if limiter_key in self.limiters:
                self.limiters.move_to_end(limiter_key)
                return self.limiters[limiter_key]
            
            # Parse rate string (e.g., "100/minute" -> 100 requests per 60 seconds)
            try:
                count, period = rate.split("/")
                count = int(count)
                
                time_period = self._parse_period(period)
                
                # Create new limiter
                limiter = AsyncLimiter(count, time_period)
                
                # Add to cache
                self.limiters[limiter_key] = limiter
                
                # Evict oldest if over limit (LRU)
                if len(self.limiters) > self.max_limiters:
                    evicted_key = next(iter(self.limiters))
                    del self.limiters[evicted_key]
                    self.logger.debug(f"Evicted rate limiter: {evicted_key}")
                
                return limiter
                
            except Exception as e:
                self.logger.error(f"Failed to create rate limiter for {rate}: {e}")
                raise ValueError(f"Invalid rate format: {rate}")
    
    def _parse_period(self, period: str) -> int:
        """Parse period string to seconds."""
        period_map = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400
        }
        
        if period not in period_map:
            raise ValueError(f"Unsupported time period: {period}")
        
        return period_map[period]
    
    async def check_rate_limit(self, key: str, rate: str) -> bool:
        """
        Check if the request is within rate limits.
        
        Args:
            key: Unique identifier for the rate limit
            rate: Rate limit string (e.g., "100/minute")
            
        Returns:
            True if within limits, False if exceeded
        """
        try:
            limiter = await self.get_limiter(key, rate)
            
            # Check capacity (non-blocking) then acquire
            if limiter.has_capacity():
                await limiter.acquire()
                self.logger.debug(f"Rate limit check passed for {key}: {rate}")
                
                # Emit request allowed event
                await self.events.emit(RateLimitEvent(
                    pattern_type=PatternType.RATE_LIMITER,
                    event_type=EventType.REQUEST_ALLOWED,
                    pattern_name=self.name,
                    user_id=key,
                    limit=rate,
                ))
                
                return True
            else:
                self.logger.warning(f"Rate limit exceeded for {key}: {rate}")
                
                # Emit request rejected event
                await self.events.emit(RateLimitEvent(
                    pattern_type=PatternType.RATE_LIMITER,
                    event_type=EventType.REQUEST_REJECTED,
                    pattern_name=self.name,
                    user_id=key,
                    limit=rate,
                ))
                
                return False
                
        except Exception as e:
            self.logger.error(f"Rate limiting error for key {key}: {e}")
            # Fail open - allow the request if rate limiting fails
            return True
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        return {
            "name": self.name,
            "active_limiters": len(self.limiters),
            "max_limiters": self.max_limiters,
            "type": "local",
        }
