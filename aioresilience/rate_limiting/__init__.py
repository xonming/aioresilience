"""
Rate Limiting Module

Provides both local (in-memory) and distributed (Redis) rate limiting.

Default import provides LocalRateLimiter:
    from aioresilience import RateLimiter  # LocalRateLimiter

Explicit imports:
    from aioresilience.rate_limiting import LocalRateLimiter, RedisRateLimiter
"""

from .local import LocalRateLimiter

# Try to import RedisRateLimiter, but don't fail if redis is not installed
try:
    from .redis import RedisRateLimiter
    _has_redis = True
except ImportError:
    _has_redis = False
    
    class RedisRateLimiter:
        """Placeholder for RedisRateLimiter when redis is not installed."""
        
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "RedisRateLimiter requires the 'redis' package. "
                "Install it with: pip install aioresilience[redis]"
            )

# Default alias
RateLimiter = LocalRateLimiter

__all__ = [
    "LocalRateLimiter",
    "RedisRateLimiter",
    "RateLimiter",  # Alias for LocalRateLimiter
]
