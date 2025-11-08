"""
Tests for Bulkhead Pattern
"""

import asyncio
import pytest
from aioresilience import (
    Bulkhead,
    BulkheadConfig,
    BulkheadFullError,
    bulkhead,
    with_bulkhead,
    get_bulkhead,
    get_all_bulkhead_metrics,
)


class TestBulkhead:
    """Tests for Bulkhead class"""
    
    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test successful execution within bulkhead"""
        bh = Bulkhead(name="test", config=BulkheadConfig(max_concurrent=5))
        
        async def func():
            return "success"
        
        result = await bh.execute(func)
        
        assert result == "success"
        metrics = bh.get_metrics()
        assert metrics["successful_requests"] == 1
        assert metrics["rejected_requests"] == 0
    
    @pytest.mark.asyncio
    async def test_concurrent_limit(self):
        """Test that concurrent execution is limited"""
        bh = Bulkhead(config=BulkheadConfig(max_concurrent=2, max_waiting=0))
        
        active_count = 0
        max_active = 0
        
        async def task():
            nonlocal active_count, max_active
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.1)
            active_count -= 1
            return "done"
        
        # Start 10 tasks
        tasks = [bh.execute(task) for _ in range(10)]
        
        # Some should be rejected since max_waiting=0
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check that concurrent limit was not exceeded
        assert max_active <= 2
        
        # Some tasks should have been rejected
        rejected = sum(1 for r in results if isinstance(r, BulkheadFullError))
        assert rejected > 0
    
    @pytest.mark.asyncio
    async def test_waiting_queue(self):
        """Test waiting queue functionality"""
        bh = Bulkhead(config=BulkheadConfig(max_concurrent=2, max_waiting=3, timeout=1.0))
        
        results = []
        
        async def task(n):
            await asyncio.sleep(0.1)
            results.append(n)
            return n
        
        # Start 5 tasks (2 running, 3 waiting)
        tasks = [bh.execute(task, i) for i in range(5)]
        
        # All should complete
        await asyncio.gather(*tasks)
        
        assert len(results) == 5
        metrics = bh.get_metrics()
        assert metrics["successful_requests"] == 5
        assert metrics["rejected_requests"] == 0
    
    @pytest.mark.asyncio
    async def test_queue_overflow(self):
        """Test that queue overflow rejects requests"""
        bh = Bulkhead(config=BulkheadConfig(max_concurrent=1, max_waiting=1))
        
        started = asyncio.Event()
        
        async def long_task():
            started.set()
            await asyncio.sleep(1.0)
            return "done"
        
        # Start first task (fills concurrent slot)
        task1 = asyncio.create_task(bh.execute(long_task))
        await started.wait()
        
        # Start second task (fills waiting queue)
        task2 = asyncio.create_task(bh.execute(long_task))
        await asyncio.sleep(0.01)
        
        # Third task should be rejected
        with pytest.raises(BulkheadFullError):
            await bh.execute(long_task)
        
        # Cleanup
        task1.cancel()
        task2.cancel()
        try:
            await task1
        except asyncio.CancelledError:
            pass
        try:
            await task2
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_timeout_waiting(self):
        """Test timeout while waiting for a slot"""
        bh = Bulkhead(config=BulkheadConfig(max_concurrent=1, max_waiting=10, timeout=0.1))
        
        async def long_task():
            await asyncio.sleep(1.0)
            return "done"
        
        # Start a long task
        task1 = asyncio.create_task(bh.execute(long_task))
        await asyncio.sleep(0.01)
        
        # This should timeout waiting
        with pytest.raises(BulkheadFullError):
            await bh.execute(long_task)
        
        # Cleanup
        task1.cancel()
        try:
            await task1
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test bulkhead as async context manager"""
        bh = Bulkhead(config=BulkheadConfig(max_concurrent=2))
        
        async with bh:
            # Do work inside bulkhead
            await asyncio.sleep(0.01)
        
        metrics = bh.get_metrics()
        assert metrics["successful_requests"] == 1
        assert metrics["current_active"] == 0
    
    @pytest.mark.asyncio
    async def test_context_manager_rejection(self):
        """Test context manager rejection when full"""
        bh = Bulkhead(config=BulkheadConfig(max_concurrent=1, max_waiting=0))
        
        # Hold the slot
        async def hold_slot():
            async with bh:
                await asyncio.sleep(1.0)
        
        task = asyncio.create_task(hold_slot())
        await asyncio.sleep(0.01)
        
        # Try to acquire - should be rejected
        with pytest.raises(BulkheadFullError):
            async with bh:
                pass
        
        # Cleanup
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_metrics_peak_active(self):
        """Test that peak active count is tracked"""
        bh = Bulkhead(config=BulkheadConfig(max_concurrent=5))
        
        async def task():
            await asyncio.sleep(0.1)
            return "done"
        
        # Run 3 concurrent tasks
        tasks = [bh.execute(task) for _ in range(3)]
        await asyncio.gather(*tasks)
        
        metrics = bh.get_metrics()
        assert metrics["peak_active"] == 3
        assert metrics["current_active"] == 0
    
    @pytest.mark.asyncio
    async def test_sync_function(self):
        """Test bulkhead with sync functions"""
        bh = Bulkhead(config=BulkheadConfig(max_concurrent=2))
        
        def sync_func(x):
            return x * 2
        
        result = await bh.execute(sync_func, 5)
        assert result == 10
    
    @pytest.mark.asyncio
    async def test_reset_metrics(self):
        """Test metrics reset"""
        bh = Bulkhead(config=BulkheadConfig(max_concurrent=5))
        
        async def func():
            return "ok"
        
        await bh.execute(func)
        
        metrics = bh.get_metrics()
        assert metrics["total_requests"] == 1
        
        bh.reset_metrics()
        
        metrics = bh.get_metrics()
        assert metrics["total_requests"] == 0
        assert metrics["successful_requests"] == 0
    
    def test_invalid_max_concurrent(self):
        """Test validation of max_concurrent"""
        with pytest.raises(ValueError, match="max_concurrent must be at least 1"):
            BulkheadConfig(max_concurrent=0)
    
    def test_invalid_max_waiting(self):
        """Test validation of max_waiting"""
        with pytest.raises(ValueError, match="max_waiting must be non-negative"):
            BulkheadConfig(max_concurrent=1, max_waiting=-1)
    
    def test_invalid_timeout(self):
        """Test validation of timeout"""
        with pytest.raises(ValueError, match="timeout must be positive or None"):
            BulkheadConfig(max_concurrent=1, timeout=0)


class TestBulkheadDecorator:
    """Tests for @bulkhead decorator"""
    
    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic instance-based decorator usage"""
        bh = Bulkhead(name="test", config=BulkheadConfig(max_concurrent=3))
        
        @with_bulkhead(bh)
        async def process(x):
            await asyncio.sleep(0.01)
            return x * 2
        
        result = await process(5)
        assert result == 10
    
    @pytest.mark.asyncio
    async def test_decorator_limiting(self):
        """Test that decorator limits concurrency"""
        active = 0
        max_active = 0
        bh = Bulkhead(name="test", config=BulkheadConfig(max_concurrent=2, max_waiting=0))
        
        @with_bulkhead(bh)
        async def task():
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.1)
            active -= 1
            return "done"
        
        # Start 5 tasks
        tasks = [asyncio.create_task(task()) for _ in range(5)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify concurrency was limited
        assert max_active <= 2
        
        # Some should be rejected
        rejected = sum(1 for r in results if isinstance(r, BulkheadFullError))
        assert rejected > 0
    
    @pytest.mark.asyncio
    async def test_decorator_metrics_access(self):
        """Test accessing metrics through instance-based decorated function"""
        bh = Bulkhead(name="test_decorator", config=BulkheadConfig(max_concurrent=5))
        
        @with_bulkhead(bh)
        async def func():
            return "ok"
        
        await func()
        
        metrics = func.bulkhead.get_metrics()
        assert metrics["successful_requests"] == 1


class TestBulkheadRegistry:
    """Tests for bulkhead registry"""
    
    @pytest.mark.asyncio
    async def test_get_bulkhead(self):
        """Test getting bulkhead from registry"""
        bh1 = await get_bulkhead("api", max_concurrent=5)
        bh2 = await get_bulkhead("api", max_concurrent=5)
        
        # Should return same instance
        assert bh1 is bh2
    
    @pytest.mark.asyncio
    async def test_get_all_metrics(self):
        """Test getting all bulkhead metrics"""
        bh1 = await get_bulkhead("api1", max_concurrent=5)
        bh2 = await get_bulkhead("api2", max_concurrent=3)
        
        async def func():
            return "ok"
        
        await bh1.execute(func)
        await bh2.execute(func)
        
        all_metrics = get_all_bulkhead_metrics()
        
        assert "api1" in all_metrics
        assert "api2" in all_metrics
        assert all_metrics["api1"]["successful_requests"] == 1
        assert all_metrics["api2"]["successful_requests"] == 1


class TestBulkheadConcurrency:
    """Tests for bulkhead behavior under high concurrency"""
    
    @pytest.mark.asyncio
    async def test_high_concurrency(self):
        """Test bulkhead under high concurrent load"""
        bh = Bulkhead(config=BulkheadConfig(max_concurrent=10, max_waiting=50, timeout=2.0))
        
        results = []
        
        async def task(n):
            await asyncio.sleep(0.01)
            results.append(n)
            return n
        
        # Start 100 tasks
        tasks = [bh.execute(task, i) for i in range(100)]
        completed = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Most should complete
        success_count = sum(1 for r in completed if not isinstance(r, Exception))
        assert success_count >= 60  # At least 60% complete
        
        metrics = bh.get_metrics()
        assert metrics["peak_active"] <= 10
    
    @pytest.mark.asyncio
    async def test_burst_traffic(self):
        """Test bulkhead with burst traffic pattern"""
        bh = Bulkhead(config=BulkheadConfig(max_concurrent=5, max_waiting=10))
        
        async def task():
            await asyncio.sleep(0.05)
            return "done"
        
        # First burst
        burst1 = [bh.execute(task) for _ in range(20)]
        results1 = await asyncio.gather(*burst1, return_exceptions=True)
        
        await asyncio.sleep(0.1)
        
        # Second burst
        burst2 = [bh.execute(task) for _ in range(20)]
        results2 = await asyncio.gather(*burst2, return_exceptions=True)
        
        # Both bursts should have similar behavior
        success1 = sum(1 for r in results1 if not isinstance(r, Exception))
        success2 = sum(1 for r in results2 if not isinstance(r, Exception))
        
        assert success1 > 0
        assert success2 > 0
    
    @pytest.mark.asyncio
    async def test_exception_in_task(self):
        """Test that exceptions don't break bulkhead"""
        bh = Bulkhead(config=BulkheadConfig(max_concurrent=3, max_waiting=5))
        
        async def failing_task():
            await asyncio.sleep(0.01)
            raise ValueError("task failed")
        
        async def successful_task():
            await asyncio.sleep(0.01)
            return "success"
        
        # Mix of failing and successful tasks
        tasks = [
            bh.execute(failing_task),
            bh.execute(successful_task),
            bh.execute(failing_task),
            bh.execute(successful_task),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify bulkhead still works
        assert isinstance(results[0], ValueError)
        assert results[1] == "success"
        assert isinstance(results[2], ValueError)
        assert results[3] == "success"
        
        # Bulkhead should track successes only
        metrics = bh.get_metrics()
        assert metrics["successful_requests"] == 2
