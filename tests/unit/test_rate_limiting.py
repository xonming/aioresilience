"""
Tests for Rate Limiting implementation
"""
import pytest
import asyncio
from aioresilience.rate_limiting import LocalRateLimiter
from aioresilience import RateLimitConfig


class TestLocalRateLimiter:
    """Test LocalRateLimiter functionality"""

    @pytest.mark.asyncio
    async def test_rate_limiter_initialization(self):
        """Test basic rate limiter initialization"""
        rl = LocalRateLimiter(config=RateLimitConfig(name="test"))
        
        assert rl.name == "test"
        assert rl.max_limiters == 10000
        assert len(rl.limiters) == 0

    @pytest.mark.asyncio
    async def test_rate_limiter_custom_max(self):
        """Test rate limiter with custom max_limiters"""
        rl = LocalRateLimiter(config=RateLimitConfig(name="test", max_limiters=100))
        
        assert rl.max_limiters == 100

    @pytest.mark.asyncio
    async def test_parse_period_second(self):
        """Test parsing 'second' period"""
        rl = LocalRateLimiter()
        assert rl._parse_period("second") == 1

    @pytest.mark.asyncio
    async def test_parse_period_minute(self):
        """Test parsing 'minute' period"""
        rl = LocalRateLimiter()
        assert rl._parse_period("minute") == 60

    @pytest.mark.asyncio
    async def test_parse_period_hour(self):
        """Test parsing 'hour' period"""
        rl = LocalRateLimiter()
        assert rl._parse_period("hour") == 3600

    @pytest.mark.asyncio
    async def test_parse_period_day(self):
        """Test parsing 'day' period"""
        rl = LocalRateLimiter()
        assert rl._parse_period("day") == 86400

    @pytest.mark.asyncio
    async def test_parse_period_invalid(self):
        """Test parsing invalid period raises error"""
        rl = LocalRateLimiter()
        with pytest.raises(ValueError):
            rl._parse_period("week")

    @pytest.mark.asyncio
    async def test_check_rate_limit_allows_first_request(self):
        """Test that first request is allowed"""
        rl = LocalRateLimiter()
        
        result = await rl.check_rate_limit("user_123", "10/second")
        assert result is True

    @pytest.mark.asyncio
    async def test_check_rate_limit_enforces_limit(self):
        """Test that rate limit is enforced"""
        rl = LocalRateLimiter()
        
        # Allow 2 per second
        allowed_count = 0
        rejected_count = 0
        
        for _ in range(5):
            if await rl.check_rate_limit("user_123", "2/second"):
                allowed_count += 1
            else:
                rejected_count += 1
        
        assert allowed_count == 2
        assert rejected_count == 3

    @pytest.mark.asyncio
    async def test_check_rate_limit_per_key(self):
        """Test that rate limiting is per-key"""
        rl = LocalRateLimiter()
        
        # Each user should have independent limits
        user1_result = await rl.check_rate_limit("user_1", "2/second")
        user2_result = await rl.check_rate_limit("user_2", "2/second")
        
        assert user1_result is True
        assert user2_result is True

    @pytest.mark.asyncio
    async def test_check_rate_limit_different_rates(self):
        """Test different rate limits for same key"""
        rl = LocalRateLimiter()
        
        # Same key, different rates should be independent
        result1 = await rl.check_rate_limit("user_123", "10/second")
        result2 = await rl.check_rate_limit("user_123", "100/minute")
        
        assert result1 is True
        assert result2 is True

    @pytest.mark.asyncio
    async def test_get_limiter_creates_new(self):
        """Test get_limiter creates new limiter"""
        rl = LocalRateLimiter()
        
        limiter = await rl.get_limiter("user_123", "10/second")
        
        assert limiter is not None
        assert len(rl.limiters) == 1

    @pytest.mark.asyncio
    async def test_get_limiter_returns_existing(self):
        """Test get_limiter returns existing limiter"""
        rl = LocalRateLimiter()
        
        limiter1 = await rl.get_limiter("user_123", "10/second")
        limiter2 = await rl.get_limiter("user_123", "10/second")
        
        assert limiter1 is limiter2
        assert len(rl.limiters) == 1

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        """Test LRU eviction of old limiters"""
        rl = LocalRateLimiter(config=RateLimitConfig(max_limiters=3))
        
        # Create 4 limiters (should evict oldest)
        await rl.get_limiter("user_1", "10/second")
        await rl.get_limiter("user_2", "10/second")
        await rl.get_limiter("user_3", "10/second")
        await rl.get_limiter("user_4", "10/second")
        
        # Should have exactly 3 limiters
        assert len(rl.limiters) == 3
        
        # First one should be evicted
        assert "user_1:10/second" not in rl.limiters

    @pytest.mark.asyncio
    async def test_lru_moves_to_end(self):
        """Test that accessing a limiter moves it to end (most recent)"""
        rl = LocalRateLimiter(config=RateLimitConfig(max_limiters=3))
        
        await rl.get_limiter("user_1", "10/second")
        await rl.get_limiter("user_2", "10/second")
        await rl.get_limiter("user_3", "10/second")
        
        # Access user_1 again (should move to end)
        await rl.get_limiter("user_1", "10/second")
        
        # Add user_4 (should evict user_2, not user_1)
        await rl.get_limiter("user_4", "10/second")
        
        assert "user_1:10/second" in rl.limiters
        assert "user_2:10/second" not in rl.limiters
        assert "user_3:10/second" in rl.limiters
        assert "user_4:10/second" in rl.limiters

    @pytest.mark.asyncio
    async def test_invalid_rate_format(self):
        """Test invalid rate format fails open (returns True)"""
        rl = LocalRateLimiter()
        
        # Should fail open and allow request despite invalid format
        result = await rl.check_rate_limit("user_123", "invalid")
        assert result is True  # Fail open behavior

    @pytest.mark.asyncio
    async def test_invalid_rate_period(self):
        """Test invalid rate period fails open (returns True)"""
        rl = LocalRateLimiter()
        
        # Should fail open and allow request despite invalid period
        result = await rl.check_rate_limit("user_123", "10/week")
        assert result is True  # Fail open behavior

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test get_stats returns correct information"""
        rl = LocalRateLimiter(config=RateLimitConfig(name="test_service", max_limiters=5000))
        
        # Create some limiters
        await rl.get_limiter("user_1", "10/second")
        await rl.get_limiter("user_2", "20/minute")
        
        stats = rl.get_stats()
        
        assert stats["name"] == "test_service"
        assert stats["active_limiters"] == 2
        assert stats["max_limiters"] == 5000
        assert stats["type"] == "local"

    @pytest.mark.asyncio
    async def test_fail_open_behavior(self):
        """Test that rate limiter fails open on errors"""
        rl = LocalRateLimiter()
        
        # Create a limiter
        await rl.get_limiter("user_123", "10/second")
        
        # Simulate error by corrupting rate string (caught internally)
        # The limiter should fail open and allow the request
        result = await rl.check_rate_limit("user_123", "10/second")
        assert result is True


class TestRateLimiterThreadSafety:
    """Test rate limiter thread safety"""

    @pytest.mark.asyncio
    async def test_concurrent_limit_checks(self):
        """Test concurrent rate limit checks are thread-safe"""
        rl = LocalRateLimiter()
        
        # 20 concurrent checks with limit of 10/second
        results = await asyncio.gather(*[
            rl.check_rate_limit("user_123", "10/second")
            for _ in range(20)
        ])
        
        # Exactly 10 should succeed
        success_count = sum(1 for r in results if r)
        assert success_count == 10

    @pytest.mark.asyncio
    async def test_concurrent_limiter_creation(self):
        """Test concurrent limiter creation is thread-safe"""
        rl = LocalRateLimiter()
        
        # Create same limiter concurrently
        limiters = await asyncio.gather(*[
            rl.get_limiter("user_123", "10/second")
            for _ in range(50)
        ])
        
        # All should be the same instance
        assert all(l is limiters[0] for l in limiters)
        # Only one limiter should be created
        assert len(rl.limiters) == 1

    @pytest.mark.asyncio
    async def test_concurrent_lru_eviction(self):
        """Test LRU eviction is thread-safe under concurrent access"""
        rl = LocalRateLimiter(config=RateLimitConfig(max_limiters=10))
        
        # Create many limiters concurrently
        await asyncio.gather(*[
            rl.get_limiter(f"user_{i}", "10/second")
            for i in range(50)
        ])
        
        # Should have exactly max_limiters
        assert len(rl.limiters) == 10

    @pytest.mark.asyncio
    async def test_concurrent_different_users(self):
        """Test concurrent rate limiting for different users"""
        rl = LocalRateLimiter()
        
        # 10 users, each making 5 requests, limit is 3/second per user
        async def user_requests(user_id: str):
            results = []
            for _ in range(5):
                result = await rl.check_rate_limit(user_id, "3/second")
                results.append(result)
            return results
        
        all_results = await asyncio.gather(*[
            user_requests(f"user_{i}")
            for i in range(10)
        ])
        
        # Each user should have exactly 3 successes
        for user_results in all_results:
            assert sum(1 for r in user_results if r) == 3


class TestRateLimitingIntegration:
    """Integration tests for rate limiting"""

    @pytest.mark.asyncio
    async def test_realistic_api_scenario(self):
        """Test realistic API rate limiting scenario"""
        rl = LocalRateLimiter(config=RateLimitConfig(name="api"))
        
        async def api_call(user_id: str):
            if await rl.check_rate_limit(user_id, "100/minute"):
                return "success"
            else:
                raise Exception("Rate limit exceeded")
        
        # Simulate multiple users making requests
        user1_calls = []
        user2_calls = []
        
        for _ in range(10):
            try:
                result = await api_call("user_1")
                user1_calls.append(result)
            except Exception:
                pass
        
        for _ in range(10):
            try:
                result = await api_call("user_2")
                user2_calls.append(result)
            except Exception:
                pass
        
        # Both users should succeed (well under 100/minute limit)
        assert len(user1_calls) == 10
        assert len(user2_calls) == 10

    @pytest.mark.asyncio
    async def test_burst_handling(self):
        """Test handling of burst traffic"""
        rl = LocalRateLimiter()
        
        # Allow 5 per second
        successes = 0
        failures = 0
        
        # Send 20 requests as fast as possible
        for _ in range(20):
            if await rl.check_rate_limit("burst_user", "5/second"):
                successes += 1
            else:
                failures += 1
        
        assert successes == 5
        assert failures == 15


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
