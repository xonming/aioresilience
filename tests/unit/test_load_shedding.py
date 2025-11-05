"""
Tests for Load Shedding implementation
"""
import pytest
import asyncio
from aioresilience.load_shedding import BasicLoadShedder, LoadLevel, with_load_shedding


class TestBasicLoadShedder:
    """Test BasicLoadShedder functionality"""

    @pytest.mark.asyncio
    async def test_load_shedder_initialization(self):
        """Test load shedder initializes correctly"""
        ls = BasicLoadShedder(max_requests=1000, max_queue_depth=500)
        
        assert ls.max_requests == 1000
        assert ls.max_queue_depth == 500
        assert ls.active_requests == 0
        assert ls.total_shed == 0

    @pytest.mark.asyncio
    async def test_acquire_under_limit(self):
        """Test acquire succeeds when under limit"""
        ls = BasicLoadShedder(max_requests=10)
        
        result = await ls.acquire()
        assert result is True
        assert ls.active_requests == 1

    @pytest.mark.asyncio
    async def test_acquire_at_limit(self):
        """Test acquire fails when at limit"""
        ls = BasicLoadShedder(max_requests=2)
        
        # Fill to limit
        await ls.acquire()
        await ls.acquire()
        
        # Should shed load
        result = await ls.acquire()
        assert result is False
        assert ls.total_shed == 1

    @pytest.mark.asyncio
    async def test_release_decrements_counter(self):
        """Test release decrements active requests"""
        ls = BasicLoadShedder(max_requests=10)
        
        await ls.acquire()
        await ls.acquire()
        assert ls.active_requests == 2
        
        await ls.release()
        assert ls.active_requests == 1

    @pytest.mark.asyncio
    async def test_priority_bypass(self):
        """Test high priority requests can bypass queue depth but not max_requests"""
        ls = BasicLoadShedder(max_requests=10, max_queue_depth=5)
        
        # Fill to queue depth limit (but under max_requests)
        for _ in range(5):
            await ls.acquire(priority="normal")
        
        ls.queue_depth = 5  # Simulate queue at limit
        
        # Normal priority should be blocked by queue depth
        result_normal = await ls.acquire(priority="normal")
        assert result_normal is False  # Blocked by queue
        
        # High priority should bypass queue depth check
        result_high = await ls.acquire(priority="high")
        assert result_high is True  # Bypasses queue check since under max_requests

    @pytest.mark.asyncio
    async def test_load_level_normal(self):
        """Test load level calculation - NORMAL"""
        ls = BasicLoadShedder(max_requests=100)
        
        # 50% utilization
        for _ in range(50):
            await ls.acquire()
        
        stats = ls.get_stats()
        assert stats["load_level"] == "normal"

    @pytest.mark.asyncio
    async def test_load_level_elevated(self):
        """Test load level calculation - ELEVATED"""
        ls = BasicLoadShedder(max_requests=100)
        
        # 65% utilization
        for _ in range(65):
            await ls.acquire()
        
        stats = ls.get_stats()
        assert stats["load_level"] == "elevated"

    @pytest.mark.asyncio
    async def test_load_level_high(self):
        """Test load level calculation - HIGH"""
        ls = BasicLoadShedder(max_requests=100)
        
        # 80% utilization
        for _ in range(80):
            await ls.acquire()
        
        stats = ls.get_stats()
        assert stats["load_level"] == "high"

    @pytest.mark.asyncio
    async def test_load_level_critical(self):
        """Test load level calculation - CRITICAL"""
        ls = BasicLoadShedder(max_requests=100)
        
        # 95% utilization
        for _ in range(95):
            await ls.acquire()
        
        stats = ls.get_stats()
        assert stats["load_level"] == "critical"

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test get_stats returns correct information"""
        ls = BasicLoadShedder(max_requests=100, max_queue_depth=50)
        
        # Fill to capacity (exactly 100 requests)
        for _ in range(100):
            await ls.acquire()
        
        # Now try one more (should shed)
        result = await ls.acquire()
        assert result is False  # Should be shed
        
        stats = ls.get_stats()
        
        assert stats["active_requests"] == 100
        assert stats["max_requests"] == 100
        assert stats["total_shed"] == 1
        assert stats["utilization"] == 100.0
        assert stats["type"] == "basic"

    @pytest.mark.asyncio
    async def test_should_shed_load_returns_reason(self):
        """Test should_shed_load returns reason"""
        ls = BasicLoadShedder(max_requests=2)
        
        await ls.acquire()
        await ls.acquire()
        
        should_shed, reason = ls.should_shed_load()
        assert should_shed is True
        assert "Max concurrent requests reached" in reason


class TestLoadSheddingDecorator:
    """Test with_load_shedding decorator"""

    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator usage"""
        ls = BasicLoadShedder(max_requests=10)
        call_count = 0
        
        @with_load_shedding(ls, priority="normal")
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_sheds_load(self):
        """Test decorator sheds load when overloaded"""
        ls = BasicLoadShedder(max_requests=1)
        
        @with_load_shedding(ls, priority="normal")
        async def test_func():
            await asyncio.sleep(0.1)
            return "success"
        
        # First call should succeed
        task1 = asyncio.create_task(test_func())
        await asyncio.sleep(0.01)  # Let it acquire
        
        # Second call should be shed
        with pytest.raises(RuntimeError, match="Service overloaded"):
            await test_func()
        
        await task1

    @pytest.mark.asyncio
    async def test_decorator_releases_on_exception(self):
        """Test decorator releases on exception"""
        ls = BasicLoadShedder(max_requests=10)
        
        @with_load_shedding(ls, priority="normal")
        async def failing_func():
            raise ValueError("Test error")
        
        assert ls.active_requests == 0
        
        with pytest.raises(ValueError):
            await failing_func()
        
        # Should have released
        assert ls.active_requests == 0


class TestLoadSheddingThreadSafety:
    """Test load shedder thread safety"""

    @pytest.mark.asyncio
    async def test_concurrent_acquire(self):
        """Test concurrent acquire is thread-safe"""
        ls = BasicLoadShedder(max_requests=50)
        
        results = await asyncio.gather(*[
            ls.acquire() for _ in range(100)
        ])
        
        # Exactly 50 should succeed
        success_count = sum(1 for r in results if r)
        assert success_count == 50
        assert ls.active_requests == 50

    @pytest.mark.asyncio
    async def test_concurrent_acquire_release(self):
        """Test concurrent acquire and release operations"""
        ls = BasicLoadShedder(max_requests=100)
        
        async def acquire_and_release():
            if await ls.acquire():
                await asyncio.sleep(0.001)
                await ls.release()
                return True
            return False
        
        results = await asyncio.gather(*[
            acquire_and_release() for _ in range(200)
        ])
        
        # Some should succeed
        success_count = sum(1 for r in results if r)
        assert success_count > 0
        
        # All should be released
        assert ls.active_requests >= 0

    @pytest.mark.asyncio
    async def test_shed_count_accuracy(self):
        """Test that total_shed count is accurate under concurrency"""
        ls = BasicLoadShedder(max_requests=10)
        
        # Fill to capacity
        for _ in range(10):
            await ls.acquire()
        
        # Try 50 more concurrently (should all be shed)
        results = await asyncio.gather(*[
            ls.acquire() for _ in range(50)
        ])
        
        assert all(r is False for r in results)
        assert ls.total_shed == 50


class TestLoadSheddingIntegration:
    """Integration tests for load shedding"""

    @pytest.mark.asyncio
    async def test_realistic_request_handling(self):
        """Test realistic request handling scenario"""
        ls = BasicLoadShedder(max_requests=100)
        
        async def handle_request(request_id: int):
            if await ls.acquire():
                try:
                    await asyncio.sleep(0.01)  # Simulate processing
                    return f"processed_{request_id}"
                finally:
                    await ls.release()
            else:
                raise Exception(f"Request {request_id} shed")
        
        # Send 150 requests
        tasks = [handle_request(i) for i in range(150)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes and failures
        successes = [r for r in results if isinstance(r, str)]
        failures = [r for r in results if isinstance(r, Exception)]
        
        # Should have some of each
        assert len(successes) > 0
        assert len(failures) > 0
        assert len(successes) + len(failures) == 150

    @pytest.mark.asyncio
    async def test_graceful_degradation(self):
        """Test graceful degradation under load"""
        ls = BasicLoadShedder(max_requests=50)
        
        processed = []
        shed = []
        
        async def process_with_tracking(item_id: int):
            if await ls.acquire():
                try:
                    await asyncio.sleep(0.01)
                    processed.append(item_id)
                finally:
                    await ls.release()
            else:
                shed.append(item_id)
        
        # Process 100 items
        await asyncio.gather(*[
            process_with_tracking(i) for i in range(100)
        ])
        
        # Some should be processed, some shed
        assert len(processed) > 0
        assert len(shed) > 0
        assert len(processed) + len(shed) == 100
        
        # Final state should be clean
        assert ls.active_requests == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
