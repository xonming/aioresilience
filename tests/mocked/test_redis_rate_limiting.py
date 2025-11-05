"""
Tests for Redis rate limiting with mocked Redis
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import time


@pytest.fixture
def mock_redis():
    """Create a mock Redis client"""
    redis = Mock()
    redis.pipeline = Mock(return_value=Mock())
    redis.ping = AsyncMock()
    redis.close = AsyncMock()
    
    # Mock pipeline operations
    pipeline = redis.pipeline.return_value
    pipeline.zremrangebyscore = Mock(return_value=pipeline)
    pipeline.zcard = Mock(return_value=pipeline)
    pipeline.zadd = Mock(return_value=pipeline)
    pipeline.expire = Mock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[None, 5, None, None])
    
    return redis


class TestRedisRateLimiter:
    """Test Redis rate limiter with mocked dependencies"""
    
    @pytest.mark.asyncio
    async def test_initialization(self, mock_redis):
        """Test Redis rate limiter initialization"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        limiter = RedisRateLimiter(name="test")
        await limiter.init_redis(redis_client=mock_redis)
        
        assert limiter.name == "test"
        assert limiter.redis_client == mock_redis
        mock_redis.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialization_with_url(self):
        """Test initialization with Redis URL"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        with patch('aioresilience.rate_limiting.redis.redis.from_url') as mock_from_url:
            mock_client = Mock()
            mock_client.ping = AsyncMock()
            mock_from_url.return_value = mock_client
            
            limiter = RedisRateLimiter(name="test")
            await limiter.init_redis(redis_url="redis://localhost:6379")
            
            mock_from_url.assert_called_once_with("redis://localhost:6379", decode_responses=False)
            mock_client.ping.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_allows_under_limit(self, mock_redis):
        """Test rate limit allows requests under limit"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        # Mock response: under limit (5 requests out of 10)
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute = AsyncMock(return_value=[None, 5, None, None])
        
        limiter = RedisRateLimiter(name="test")
        await limiter.init_redis(redis_client=mock_redis)
        
        result = await limiter.check_rate_limit("user_1", "10/second")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_rejects_over_limit(self, mock_redis):
        """Test rate limit rejects requests over limit"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        # Mock response: over limit (11 requests out of 10)
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute = AsyncMock(return_value=[None, 11, None, None])
        
        limiter = RedisRateLimiter(name="test")
        await limiter.init_redis(redis_client=mock_redis)
        
        result = await limiter.check_rate_limit("user_1", "10/second")
        assert result is False
    
    @pytest.mark.asyncio
    async def test_parse_period(self, mock_redis):
        """Test period parsing"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        limiter = RedisRateLimiter(name="test")
        await limiter.init_redis(redis_client=mock_redis)
        
        assert limiter._parse_period("second") == 1
        assert limiter._parse_period("minute") == 60
        assert limiter._parse_period("hour") == 3600
        assert limiter._parse_period("day") == 86400
    
    @pytest.mark.asyncio
    async def test_redis_key_format(self, mock_redis):
        """Test Redis key format"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute = AsyncMock(return_value=[None, 5, None, None])
        
        limiter = RedisRateLimiter(name="api")
        await limiter.init_redis(redis_client=mock_redis)
        
        await limiter.check_rate_limit("user_123", "100/minute")
        
        # Verify zremrangebyscore was called with correct key
        call_args = pipeline.zremrangebyscore.call_args
        assert call_args[0][0] == "rate_limit:api:user_123:100/minute"
    
    @pytest.mark.asyncio
    async def test_close_connection(self, mock_redis):
        """Test closing Redis connection"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        limiter = RedisRateLimiter(name="test")
        await limiter.init_redis(redis_client=mock_redis)
        
        await limiter.close()
        mock_redis.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_stats(self, mock_redis):
        """Test get_stats returns correct info"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        limiter = RedisRateLimiter(name="test_service")
        await limiter.init_redis(redis_client=mock_redis)
        
        stats = limiter.get_stats()
        
        assert stats["name"] == "test_service"
        assert stats["type"] == "redis"
        assert stats["connected"] is True
    
    @pytest.mark.asyncio
    async def test_fail_open_on_redis_error(self, mock_redis):
        """Test fails open when Redis errors occur"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        # Mock Redis to raise exception
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute = AsyncMock(side_effect=Exception("Redis error"))
        
        limiter = RedisRateLimiter(name="test")
        await limiter.init_redis(redis_client=mock_redis)
        
        # Should fail open (allow request) on error
        result = await limiter.check_rate_limit("user_1", "10/second")
        assert result is True
    
    @pytest.mark.asyncio
    async def test_not_initialized_raises_error(self):
        """Test using limiter without initialization raises error"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        limiter = RedisRateLimiter(name="test")
        
        with pytest.raises(RuntimeError, match="Redis client not initialized"):
            await limiter.check_rate_limit("user_1", "10/second")
    
    @pytest.mark.asyncio
    async def test_init_without_url_or_client_raises_error(self):
        """Test initialization without URL or client raises error"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        limiter = RedisRateLimiter(name="test")
        
        with pytest.raises(ValueError, match="Either redis_url or redis_client must be provided"):
            await limiter.init_redis()
    
    @pytest.mark.asyncio
    async def test_multiple_users_different_keys(self, mock_redis):
        """Test different users get different Redis keys"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute = AsyncMock(return_value=[None, 5, None, None])
        
        limiter = RedisRateLimiter(name="api")
        await limiter.init_redis(redis_client=mock_redis)
        
        await limiter.check_rate_limit("user_1", "100/minute")
        key1 = pipeline.zremrangebyscore.call_args[0][0]
        
        await limiter.check_rate_limit("user_2", "100/minute")
        key2 = pipeline.zremrangebyscore.call_args[0][0]
        
        assert key1 != key2
        assert "user_1" in key1
        assert "user_2" in key2
    
    @pytest.mark.asyncio
    async def test_sliding_window_cleanup(self, mock_redis):
        """Test sliding window removes old entries"""
        from aioresilience.rate_limiting import RedisRateLimiter
        
        pipeline = mock_redis.pipeline.return_value
        pipeline.execute = AsyncMock(return_value=[None, 5, None, None])
        
        limiter = RedisRateLimiter(name="test")
        await limiter.init_redis(redis_client=mock_redis)
        
        await limiter.check_rate_limit("user_1", "10/second")
        
        # Verify zremrangebyscore was called to remove old entries
        pipeline.zremrangebyscore.assert_called()
        call_args = pipeline.zremrangebyscore.call_args[0]
        assert call_args[1] == 0  # min score
        # max score should be current_time - window (in milliseconds)
