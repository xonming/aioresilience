"""
Redis-Based Distributed Rate Limiter

Uses Redis for distributed rate limiting across multiple instances.

Dependencies:
- redis (required) - pip install redis

Install:
    pip install aioresilience[redis]
"""

import asyncio
import time
from typing import Optional
import logging

try:
    import redis.asyncio as redis
    _has_redis = True
except ImportError:
    _has_redis = False
    redis = None

logger = logging.getLogger(__name__)


class RedisRateLimiter:
    """
    Redis-backed distributed rate limiter.
    
    Suitable for multi-instance applications where rate limits
    need to be shared across all instances.
    
    Features:
    - Distributed rate limiting
    - Sliding window algorithm
    - Atomic operations
    - Automatic key expiration
    
    Example:
        rate_limiter = RedisRateLimiter(name="api")
        await rate_limiter.init_redis(redis_url="redis://localhost:6379")
        
        # Check rate limit
        if await rate_limiter.check_rate_limit("user_123", "100/minute"):
            # Process request
        else:
            raise Exception("Rate limit exceeded")
    """
    
    def __init__(self, name: str = "default"):
        """
        Initialize Redis rate limiter.
        
        Args:
            name: Name for this rate limiter (for logging and Redis keys)
        """
        if not _has_redis:
            raise ImportError(
                "RedisRateLimiter requires the 'redis' package. "
                "Install it with: pip install redis"
            )
        
        self.name = name
        self.redis_client: Optional[redis.Redis] = None
        self.logger = logger
    
    async def init_redis(self, redis_url: str = None, redis_client = None):
        """
        Initialize Redis client.
        
        Args:
            redis_url: Redis connection URL (if creating new client)
            redis_client: Existing Redis client to reuse
        """
        try:
            if redis_client:
                self.redis_client = redis_client
            elif redis_url:
                self.redis_client = redis.from_url(redis_url, decode_responses=False)
            else:
                raise ValueError("Either redis_url or redis_client must be provided")
            
            await self.redis_client.ping()
            self.logger.info(f"{self.name}: Redis rate limiter initialized")
        except Exception as e:
            self.logger.error(f"{self.name}: Failed to initialize Redis: {e}")
            raise
    
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
        Check rate limit using Redis sliding window algorithm.
        
        Uses sorted sets (ZSET) to track requests in a time window.
        
        Args:
            key: Unique identifier for the rate limit
            rate: Rate limit string (e.g., "100/minute")
            
        Returns:
            True if within limits, False if exceeded
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not initialized. Call init_redis() first.")
        
        try:
            # Parse rate string
            count, period = rate.split("/")
            count = int(count)
            time_period = self._parse_period(period)
            
            # Create Redis key for this rate limit
            redis_key = f"rate_limit:{self.name}:{key}:{rate}"
            current_time = int(time.time() * 1000)  # Milliseconds for precision
            window_start = current_time - (time_period * 1000)
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Remove expired entries
            pipe.zremrangebyscore(redis_key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(redis_key)
            
            # Add current request
            pipe.zadd(redis_key, {str(current_time): current_time})
            
            # Set expiration
            pipe.expire(redis_key, time_period + 10)  # Add buffer
            
            # Execute pipeline
            results = await pipe.execute()
            current_count = results[1]  # Result from zcard
            
            # Check if we're within limits
            if current_count < count:
                self.logger.debug(f"Rate limit check passed for {key}: {current_count + 1}/{count}")
                return True
            else:
                self.logger.warning(f"Rate limit exceeded for {key}: {current_count}/{count}")
                return False
                
        except Exception as e:
            self.logger.error(f"Redis rate limiting error for key {key}: {e}")
            # Fail open - allow the request if Redis fails
            return True
    
    async def close(self):
        """Close Redis connection."""
        if self.redis_client:
            await self.redis_client.close()
            self.logger.info(f"{self.name}: Redis connection closed")
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics"""
        return {
            "name": self.name,
            "type": "redis",
            "connected": self.redis_client is not None,
        }
