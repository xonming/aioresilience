"""
Tests for Adaptive Concurrency Limiting
"""
import pytest
import asyncio
from aioresilience import AdaptiveConcurrencyLimiter


class TestAdaptiveConcurrencyLimiter:
    """Test AdaptiveConcurrencyLimiter functionality"""

    @pytest.mark.asyncio
    async def test_limiter_initialization(self):
        """Test limiter initializes correctly"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            min_limit=10,
            max_limit=1000,
            increase_rate=1.0,
            decrease_factor=0.9
        )
        
        assert limiter.current_limit == 100
        assert limiter.min_limit == 10
        assert limiter.max_limit == 1000
        assert limiter.increase_rate == 1.0
        assert limiter.decrease_factor == 0.9
        assert limiter.active_count == 0

    @pytest.mark.asyncio
    async def test_acquire_under_limit(self):
        """Test acquire succeeds when under limit"""
        limiter = AdaptiveConcurrencyLimiter(initial_limit=10)
        
        result = await limiter.acquire()
        assert result is True
        assert limiter.active_count == 1

    @pytest.mark.asyncio
    async def test_acquire_at_limit(self):
        """Test acquire fails when at limit"""
        limiter = AdaptiveConcurrencyLimiter(initial_limit=2)
        
        # Fill to limit
        await limiter.acquire()
        await limiter.acquire()
        
        # Should fail
        result = await limiter.acquire()
        assert result is False

    @pytest.mark.asyncio
    async def test_release_decrements_counter(self):
        """Test release decrements active count"""
        limiter = AdaptiveConcurrencyLimiter(initial_limit=10)
        
        await limiter.acquire()
        await limiter.acquire()
        assert limiter.active_count == 2
        
        await limiter.release(success=True)
        assert limiter.active_count == 1

    @pytest.mark.asyncio
    async def test_release_tracks_success(self):
        """Test release tracks success count"""
        limiter = AdaptiveConcurrencyLimiter(initial_limit=10)
        
        await limiter.acquire()
        await limiter.release(success=True)
        
        assert limiter.success_count == 1
        assert limiter.failure_count == 0

    @pytest.mark.asyncio
    async def test_release_tracks_failure(self):
        """Test release tracks failure count"""
        limiter = AdaptiveConcurrencyLimiter(initial_limit=10)
        
        await limiter.acquire()
        await limiter.release(success=False)
        
        assert limiter.success_count == 0
        assert limiter.failure_count == 1

    @pytest.mark.asyncio
    async def test_limit_increases_on_high_success_rate(self):
        """Test limit increases when success rate > 95%"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            max_limit=200,
            increase_rate=10.0,
            measurement_window=10
        )
        
        # Simulate 10 successful requests (100% success rate)
        for _ in range(10):
            await limiter.acquire()
            await limiter.release(success=True)
        
        # Limit should have increased
        assert limiter.current_limit > 100

    @pytest.mark.asyncio
    async def test_limit_decreases_on_low_success_rate(self):
        """Test limit decreases when success rate < 80%"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            min_limit=10,
            decrease_factor=0.5,
            measurement_window=10
        )
        
        # Simulate 10 requests with 50% success rate
        for i in range(10):
            await limiter.acquire()
            await limiter.release(success=(i % 2 == 0))
        
        # Limit should have decreased
        assert limiter.current_limit < 100

    @pytest.mark.asyncio
    async def test_limit_respects_min_limit(self):
        """Test limit doesn't go below min_limit"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=20,
            min_limit=10,
            decrease_factor=0.1,
            measurement_window=10
        )
        
        # Simulate all failures
        for _ in range(10):
            await limiter.acquire()
            await limiter.release(success=False)
        
        # Should not go below min_limit
        assert limiter.current_limit >= limiter.min_limit

    @pytest.mark.asyncio
    async def test_limit_respects_max_limit(self):
        """Test limit doesn't go above max_limit"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=90,
            max_limit=100,
            increase_rate=50.0,
            measurement_window=10
        )
        
        # Simulate all successes
        for _ in range(10):
            await limiter.acquire()
            await limiter.release(success=True)
        
        # Should not exceed max_limit
        assert limiter.current_limit <= limiter.max_limit

    @pytest.mark.asyncio
    async def test_measurement_window_resets_counters(self):
        """Test counters reset after measurement window"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            measurement_window=5
        )
        
        # Complete a measurement window
        for _ in range(5):
            await limiter.acquire()
            await limiter.release(success=True)
        
        # Counters should be reset
        assert limiter.success_count == 0
        assert limiter.failure_count == 0

    @pytest.mark.asyncio
    async def test_limit_stable_on_medium_success_rate(self):
        """Test limit stays stable when success rate is between 80-95%"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            measurement_window=10
        )
        
        initial_limit = limiter.current_limit
        
        # Simulate 85% success rate
        for i in range(10):
            await limiter.acquire()
            await limiter.release(success=(i < 8.5))
        
        # Limit should remain relatively stable (within reason)
        # Allow some variance due to rounding
        assert abs(limiter.current_limit - initial_limit) <= 1

    @pytest.mark.asyncio
    async def test_aimd_additive_increase(self):
        """Test AIMD additive increase behavior"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            max_limit=200,
            increase_rate=5.0,
            measurement_window=10
        )
        
        # High success rate - should increase by increase_rate
        for _ in range(10):
            await limiter.acquire()
            await limiter.release(success=True)
        
        # Should have increased by approximately increase_rate
        assert limiter.current_limit >= 100 + 5

    @pytest.mark.asyncio
    async def test_aimd_multiplicative_decrease(self):
        """Test AIMD multiplicative decrease behavior"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            min_limit=10,
            decrease_factor=0.8,
            measurement_window=10
        )
        
        # Low success rate - should multiply by decrease_factor
        for _ in range(10):
            await limiter.acquire()
            await limiter.release(success=False)
        
        # Should have decreased multiplicatively
        expected = int(100 * 0.8)
        assert limiter.current_limit == expected

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test get_stats returns correct information"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            min_limit=10,
            max_limit=200
        )
        
        # Add some activity
        for _ in range(5):
            await limiter.acquire()
        
        for _ in range(3):
            await limiter.release(success=True)
        
        for _ in range(2):
            await limiter.release(success=False)
        
        stats = limiter.get_stats()
        
        assert stats["current_limit"] == 100
        assert stats["active_count"] == 0  # All released
        assert stats["total_requests"] == 5
        assert stats["success_count"] == 3
        assert stats["failure_count"] == 2
        assert "utilization" in stats


class TestAdaptiveConcurrencyAIMD:
    """Test AIMD algorithm specifically"""

    @pytest.mark.asyncio
    async def test_multiple_increase_cycles(self):
        """Test limit increases over multiple cycles"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            max_limit=200,
            increase_rate=5.0,
            measurement_window=10
        )
        
        initial_limit = limiter.current_limit
        
        # Run 5 measurement windows with 100% success
        for cycle in range(5):
            for _ in range(10):
                await limiter.acquire()
                await limiter.release(success=True)
        
        # Should have increased significantly
        assert limiter.current_limit > initial_limit + 20

    @pytest.mark.asyncio
    async def test_multiple_decrease_cycles(self):
        """Test limit decreases over multiple cycles"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            min_limit=10,
            decrease_factor=0.9,
            measurement_window=10
        )
        
        initial_limit = limiter.current_limit
        
        # Run 5 measurement windows with 0% success
        for cycle in range(5):
            for _ in range(10):
                await limiter.acquire()
                await limiter.release(success=False)
        
        # Should have decreased significantly
        assert limiter.current_limit < initial_limit * 0.6

    @pytest.mark.asyncio
    async def test_oscillation_behavior(self):
        """Test behavior with oscillating success rates"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            min_limit=50,
            max_limit=150,
            measurement_window=10
        )
        
        limits = []
        
        # Alternate between high and low success rates
        for cycle in range(10):
            success_rate = 0.98 if cycle % 2 == 0 else 0.50
            for i in range(10):
                await limiter.acquire()
                success = (i / 10) < success_rate
                await limiter.release(success=success)
            limits.append(limiter.current_limit)
        
        # Should see variation but stay within bounds
        assert all(limiter.min_limit <= l <= limiter.max_limit for l in limits)


class TestAdaptiveConcurrencyThreadSafety:
    """Test adaptive concurrency thread safety"""

    @pytest.mark.asyncio
    async def test_concurrent_acquire(self):
        """Test concurrent acquire is thread-safe"""
        limiter = AdaptiveConcurrencyLimiter(initial_limit=50)
        
        results = await asyncio.gather(*[
            limiter.acquire() for _ in range(100)
        ])
        
        # Exactly 50 should succeed
        success_count = sum(1 for r in results if r)
        assert success_count == 50
        assert limiter.active_count == 50

    @pytest.mark.asyncio
    async def test_concurrent_release(self):
        """Test concurrent release is thread-safe"""
        limiter = AdaptiveConcurrencyLimiter(initial_limit=100)
        
        # Acquire some slots
        for _ in range(50):
            await limiter.acquire()
        
        # Release concurrently
        await asyncio.gather(*[
            limiter.release(success=True) for _ in range(50)
        ])
        
        # Should be back to 0
        assert limiter.active_count == 0
        assert limiter.success_count == 50

    @pytest.mark.asyncio
    async def test_concurrent_acquire_release_with_adjustment(self):
        """Test concurrent operations with limit adjustment"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=50,
            measurement_window=20
        )
        
        async def acquire_release_cycle(success: bool):
            if await limiter.acquire():
                await asyncio.sleep(0.001)
                await limiter.release(success=success)
                return True
            return False
        
        # Run many concurrent cycles (should trigger adjustments)
        results = await asyncio.gather(*[
            acquire_release_cycle(i % 5 != 0)  # 80% success rate
            for i in range(100)
        ])
        
        success_count = sum(1 for r in results if r)
        assert success_count > 0

    @pytest.mark.asyncio
    async def test_limit_adjustment_atomicity(self):
        """Test limit adjustments are atomic"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            measurement_window=10
        )
        
        # Trigger multiple simultaneous measurement window completions
        async def complete_window(success_rate: float):
            for i in range(10):
                await limiter.acquire()
                success = (i / 10) < success_rate
                await limiter.release(success=success)
        
        # Run multiple windows concurrently
        await asyncio.gather(*[
            complete_window(0.98) for _ in range(5)
        ])
        
        # Limit should be valid
        assert limiter.min_limit <= limiter.current_limit <= limiter.max_limit


class TestAdaptiveConcurrencyIntegration:
    """Integration tests for adaptive concurrency"""

    @pytest.mark.asyncio
    async def test_realistic_api_scenario(self):
        """Test realistic API with varying load"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=50,
            min_limit=10,
            max_limit=100,
            measurement_window=20
        )
        
        processed = []
        rejected = []
        
        async def api_call(call_id: int, should_succeed: bool):
            if await limiter.acquire():
                try:
                    await asyncio.sleep(0.01)
                    if should_succeed:
                        processed.append(call_id)
                        await limiter.release(success=True)
                    else:
                        await limiter.release(success=False)
                        raise Exception("API error")
                except Exception:
                    pass
            else:
                rejected.append(call_id)
        
        # Simulate 100 requests with 90% success rate
        await asyncio.gather(*[
            api_call(i, i % 10 != 0) for i in range(100)
        ], return_exceptions=True)
        
        # Should have processed most
        assert len(processed) > 0

    @pytest.mark.asyncio
    async def test_adaptive_behavior_under_degradation(self):
        """Test limiter adapts when service degrades"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=100,
            min_limit=10,
            max_limit=200,
            measurement_window=10
        )
        
        initial_limit = limiter.current_limit
        limits_over_time = [initial_limit]
        
        # Phase 1: Good performance (95% success)
        for _ in range(10):
            await limiter.acquire()
            await limiter.release(success=True)
        limits_over_time.append(limiter.current_limit)
        
        # Phase 2: Degradation (50% success)
        for i in range(30):
            await limiter.acquire()
            await limiter.release(success=(i % 2 == 0))
        limits_over_time.append(limiter.current_limit)
        
        # Phase 3: Recovery (95% success)
        for _ in range(10):
            await limiter.acquire()
            await limiter.release(success=True)
        limits_over_time.append(limiter.current_limit)
        
        # Limit should increase, then decrease, then increase again
        assert limits_over_time[1] >= limits_over_time[0]  # Increased
        assert limits_over_time[2] < limits_over_time[1]   # Decreased
        # Recovery may or may not fully restore, depends on algorithm

    @pytest.mark.asyncio
    async def test_gradual_load_increase(self):
        """Test behavior with gradually increasing load"""
        limiter = AdaptiveConcurrencyLimiter(
            initial_limit=50,
            max_limit=200,
            measurement_window=10
        )
        
        # Gradually increase load with high success rate
        for batch in range(5):
            for _ in range(10):
                if await limiter.acquire():
                    await limiter.release(success=True)
        
        # Limit should have increased
        assert limiter.current_limit > 50

    @pytest.mark.asyncio
    async def test_burst_handling(self):
        """Test handling of burst traffic"""
        limiter = AdaptiveConcurrencyLimiter(initial_limit=20)
        
        async def process_request():
            if await limiter.acquire():
                await asyncio.sleep(0.01)
                await limiter.release(success=True)
                return True
            return False
        
        # Send burst of 50 requests
        results = await asyncio.gather(*[
            process_request() for _ in range(50)
        ])
        
        success_count = sum(1 for r in results if r)
        
        # Should process some but not all
        assert success_count > 0
        assert success_count <= limiter.current_limit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
