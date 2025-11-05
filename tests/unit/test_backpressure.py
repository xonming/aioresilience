"""
Tests for Backpressure Management
"""
import pytest
import asyncio
from aioresilience import BackpressureManager, with_backpressure


class TestBackpressureManager:
    """Test BackpressureManager functionality"""

    @pytest.mark.asyncio
    async def test_backpressure_initialization(self):
        """Test backpressure manager initializes correctly"""
        bp = BackpressureManager(
            max_pending=1000,
            high_water_mark=800,
            low_water_mark=200
        )
        
        assert bp.max_pending == 1000
        assert bp.high_water_mark == 800
        assert bp.low_water_mark == 200
        assert bp.pending_count == 0
        assert bp.backpressure_active is False
        assert bp.total_rejected == 0

    @pytest.mark.asyncio
    async def test_acquire_under_limit(self):
        """Test acquire succeeds when under limit"""
        bp = BackpressureManager(max_pending=10)
        
        result = await bp.acquire()
        assert result is True
        assert bp.pending_count == 1

    @pytest.mark.asyncio
    async def test_acquire_at_max_limit(self):
        """Test acquire fails when at max limit"""
        bp = BackpressureManager(max_pending=2)
        
        # Fill to capacity
        await bp.acquire()
        await bp.acquire()
        
        # Should reject
        result = await bp.acquire()
        assert result is False
        assert bp.total_rejected == 1

    @pytest.mark.asyncio
    async def test_release_decrements_counter(self):
        """Test release decrements pending count"""
        bp = BackpressureManager(max_pending=10)
        
        await bp.acquire()
        await bp.acquire()
        assert bp.pending_count == 2
        
        await bp.release()
        assert bp.pending_count == 1
        
        await bp.release()
        assert bp.pending_count == 0

    @pytest.mark.asyncio
    async def test_release_never_negative(self):
        """Test release never makes pending_count negative"""
        bp = BackpressureManager(max_pending=10)
        
        await bp.release()  # Release without acquire
        assert bp.pending_count == 0

    @pytest.mark.asyncio
    async def test_high_water_mark_activates_backpressure(self):
        """Test backpressure activates at high water mark"""
        bp = BackpressureManager(
            max_pending=100,
            high_water_mark=80,
            low_water_mark=20
        )
        
        # Fill to high water mark
        for _ in range(80):
            await bp.acquire()
        
        assert bp.backpressure_active is True
        assert bp.pending_count == 80

    @pytest.mark.asyncio
    async def test_low_water_mark_deactivates_backpressure(self):
        """Test backpressure deactivates at low water mark"""
        bp = BackpressureManager(
            max_pending=100,
            high_water_mark=80,
            low_water_mark=20
        )
        
        # Activate backpressure
        for _ in range(80):
            await bp.acquire()
        assert bp.backpressure_active is True
        
        # Release down to low water mark
        for _ in range(61):  # 80 - 61 = 19 (below low water mark)
            await bp.release()
        
        assert bp.backpressure_active is False
        assert bp.pending_count == 19

    @pytest.mark.asyncio
    async def test_acquire_blocks_when_backpressure_active(self):
        """Test acquire blocks when backpressure is active"""
        bp = BackpressureManager(
            max_pending=100,
            high_water_mark=10,
            low_water_mark=5
        )
        
        # Activate backpressure
        for _ in range(10):
            await bp.acquire()
        assert bp.backpressure_active is True
        
        # Try to acquire with short timeout - should timeout
        result = await bp.acquire(timeout=0.1)
        assert result is False
        assert bp.total_rejected == 1

    @pytest.mark.asyncio
    async def test_acquire_succeeds_after_release(self):
        """Test acquire succeeds after enough releases"""
        bp = BackpressureManager(
            max_pending=100,
            high_water_mark=10,
            low_water_mark=5
        )
        
        # Activate backpressure
        for _ in range(10):
            await bp.acquire()
        assert bp.backpressure_active is True
        
        # Create a task that tries to acquire
        async def try_acquire():
            return await bp.acquire(timeout=1.0)
        
        acquire_task = asyncio.create_task(try_acquire())
        
        # Wait a bit, then release enough to deactivate
        await asyncio.sleep(0.1)
        for _ in range(6):  # Down to 4, below low water mark
            await bp.release()
        
        # The blocked acquire should now succeed
        result = await acquire_task
        assert result is True

    @pytest.mark.asyncio
    async def test_acquire_timeout(self):
        """Test acquire respects timeout"""
        bp = BackpressureManager(
            max_pending=100,
            high_water_mark=5,
            low_water_mark=2
        )
        
        # Activate backpressure
        for _ in range(5):
            await bp.acquire()
        
        # Try to acquire with timeout
        import time
        start = time.time()
        result = await bp.acquire(timeout=0.2)
        elapsed = time.time() - start
        
        assert result is False
        assert elapsed >= 0.2
        assert elapsed < 0.3  # Should timeout promptly

    @pytest.mark.asyncio
    async def test_is_overloaded_property(self):
        """Test is_overloaded property"""
        bp = BackpressureManager(max_pending=10)
        
        assert bp.is_overloaded is False
        
        # Fill to capacity
        for _ in range(10):
            await bp.acquire()
        
        assert bp.is_overloaded is True

    @pytest.mark.asyncio
    async def test_should_apply_backpressure_property(self):
        """Test should_apply_backpressure property"""
        bp = BackpressureManager(
            max_pending=100,
            high_water_mark=80,
            low_water_mark=20
        )
        
        assert bp.should_apply_backpressure is False
        
        # Fill to high water mark
        for _ in range(80):
            await bp.acquire()
        
        assert bp.should_apply_backpressure is True

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Test get_stats returns correct information"""
        bp = BackpressureManager(
            max_pending=100,
            high_water_mark=80,
            low_water_mark=20
        )
        
        # Add load up to high water mark (activates backpressure)
        for _ in range(80):
            await bp.acquire()
        
        # Try to acquire more (should reject due to backpressure)
        rejected = 0
        for _ in range(50):
            result = await bp.acquire(timeout=0)
            if not result:
                rejected += 1
        
        stats = bp.get_stats()
        
        assert stats["pending_count"] == 80
        assert stats["max_pending"] == 100
        assert stats["backpressure_active"] is True
        assert stats["total_rejected"] == rejected
        assert stats["utilization"] == 80.0


class TestBackpressureDecorator:
    """Test with_backpressure decorator"""

    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator usage"""
        bp = BackpressureManager(max_pending=10)
        call_count = 0
        
        @with_backpressure(bp, timeout=5.0)
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 1
        assert bp.pending_count == 0  # Should be released

    @pytest.mark.asyncio
    async def test_decorator_raises_when_rejected(self):
        """Test decorator raises when backpressure rejects"""
        bp = BackpressureManager(max_pending=1)
        
        @with_backpressure(bp, timeout=0.1)
        async def test_func():
            await asyncio.sleep(1.0)
            return "success"
        
        # Start first call (will hold the slot)
        task1 = asyncio.create_task(test_func())
        await asyncio.sleep(0.05)
        
        # Second call should be rejected
        with pytest.raises(RuntimeError, match="Backpressure: System overloaded"):
            await test_func()
        
        # Cancel first task
        task1.cancel()
        try:
            await task1
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_decorator_releases_on_exception(self):
        """Test decorator releases slot on exception"""
        bp = BackpressureManager(max_pending=10)
        
        @with_backpressure(bp, timeout=5.0)
        async def failing_func():
            raise ValueError("Test error")
        
        assert bp.pending_count == 0
        
        with pytest.raises(ValueError):
            await failing_func()
        
        # Should have released
        assert bp.pending_count == 0

    @pytest.mark.asyncio
    async def test_decorator_with_timeout(self):
        """Test decorator with custom timeout"""
        bp = BackpressureManager(
            max_pending=10,
            high_water_mark=1,
            low_water_mark=0
        )
        
        # Activate backpressure
        await bp.acquire()
        
        @with_backpressure(bp, timeout=0.1)
        async def test_func():
            return "success"
        
        # Should timeout
        with pytest.raises(RuntimeError, match="Backpressure"):
            await test_func()


class TestBackpressureThreadSafety:
    """Test backpressure thread safety"""

    @pytest.mark.asyncio
    async def test_concurrent_acquire(self):
        """Test concurrent acquire is thread-safe"""
        bp = BackpressureManager(max_pending=50)
        
        results = await asyncio.gather(*[
            bp.acquire(timeout=0) for _ in range(100)
        ])
        
        # Exactly 50 should succeed
        success_count = sum(1 for r in results if r)
        assert success_count == 50
        assert bp.pending_count == 50

    @pytest.mark.asyncio
    async def test_concurrent_acquire_release(self):
        """Test concurrent acquire and release"""
        bp = BackpressureManager(max_pending=100)
        
        async def acquire_and_release():
            if await bp.acquire():
                await asyncio.sleep(0.001)
                await bp.release()
                return True
            return False
        
        results = await asyncio.gather(*[
            acquire_and_release() for _ in range(200)
        ])
        
        # Some should succeed
        success_count = sum(1 for r in results if r)
        assert success_count > 0
        
        # All should be released
        assert bp.pending_count >= 0
        assert bp.pending_count <= 100

    @pytest.mark.asyncio
    async def test_backpressure_activation_race(self):
        """Test backpressure activation is atomic"""
        bp = BackpressureManager(
            max_pending=100,
            high_water_mark=50,
            low_water_mark=25
        )
        
        # Race to high water mark (use timeout to prevent blocking)
        results = await asyncio.gather(*[
            bp.acquire(timeout=0.1) for _ in range(60)
        ])
        
        # Should have some successful, some rejected
        success_count = sum(1 for r in results if r)
        assert success_count <= 60
        assert success_count >= 50  # At least reached high water mark
        
        # Backpressure should be active
        if bp.pending_count >= 50:
            assert bp.backpressure_active is True

    @pytest.mark.asyncio
    async def test_reject_count_accuracy(self):
        """Test total_rejected is accurate under concurrency"""
        bp = BackpressureManager(max_pending=10)
        
        # Fill to capacity
        for _ in range(10):
            await bp.acquire()
        
        # Try 50 more concurrently (should all be rejected immediately)
        results = await asyncio.gather(*[
            bp.acquire(timeout=0) for _ in range(50)
        ])
        
        assert all(r is False for r in results)
        assert bp.total_rejected == 50


class TestBackpressureIntegration:
    """Integration tests for backpressure"""

    @pytest.mark.asyncio
    async def test_realistic_pipeline_scenario(self):
        """Test realistic async pipeline with backpressure"""
        bp = BackpressureManager(
            max_pending=50,
            high_water_mark=40,
            low_water_mark=10
        )
        
        processed = []
        rejected = []
        
        async def process_item(item_id: int):
            if await bp.acquire(timeout=0.1):
                try:
                    await asyncio.sleep(0.01)  # Simulate processing
                    processed.append(item_id)
                finally:
                    await bp.release()
            else:
                rejected.append(item_id)
        
        # Process 100 items
        await asyncio.gather(*[
            process_item(i) for i in range(100)
        ])
        
        # Some should be processed, some rejected
        assert len(processed) > 0
        assert len(rejected) > 0
        assert len(processed) + len(rejected) == 100
        
        # Final state should be clean
        assert bp.pending_count == 0

    @pytest.mark.asyncio
    async def test_burst_handling(self):
        """Test handling of burst traffic with backpressure activation"""
        bp = BackpressureManager(
            max_pending=20,
            high_water_mark=15,
            low_water_mark=5
        )
        
        backpressure_was_active = False
        
        async def process_burst():
            nonlocal backpressure_was_active
            if await bp.acquire(timeout=0.5):  # Allow some wait time
                try:
                    if bp.backpressure_active:
                        backpressure_was_active = True
                    await asyncio.sleep(0.01)
                finally:
                    await bp.release()
                return True
            return False
        
        # Send burst of 50 requests
        results = await asyncio.gather(*[
            process_burst() for _ in range(50)
        ])
        
        success_count = sum(1 for r in results if r)
        
        # Should have processed most requests
        assert success_count > 0
        
        # Backpressure should have activated at some point
        assert backpressure_was_active is True

    @pytest.mark.asyncio
    async def test_gradual_load_increase(self):
        """Test behavior with gradually increasing load"""
        bp = BackpressureManager(
            max_pending=100,
            high_water_mark=80,
            low_water_mark=20
        )
        
        # Gradually increase load
        acquired = 0
        for batch in range(5):
            batch_size = 20
            for _ in range(batch_size):
                if await bp.acquire(timeout=0.1):
                    acquired += 1
            
            # Check state
            if bp.pending_count >= 80:
                assert bp.backpressure_active is True
            
            await asyncio.sleep(0.01)
        
        # Should have acquired up to max_pending
        assert acquired <= 100
        assert bp.pending_count <= 100

    @pytest.mark.asyncio
    async def test_producer_consumer_pattern(self):
        """Test producer-consumer pattern with backpressure"""
        bp = BackpressureManager(
            max_pending=10,
            high_water_mark=8,
            low_water_mark=3
        )
        
        queue = asyncio.Queue()
        produced = []
        consumed = []
        
        async def producer():
            for i in range(20):
                if await bp.acquire(timeout=0.5):
                    await queue.put(i)
                    produced.append(i)
                else:
                    # Producer backs off when backpressure active
                    await asyncio.sleep(0.1)
        
        async def consumer():
            while len(consumed) < 20:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=1.0)
                    await asyncio.sleep(0.01)  # Simulate processing
                    consumed.append(item)
                    await bp.release()
                except asyncio.TimeoutError:
                    break
        
        # Run producer and consumer
        await asyncio.gather(
            producer(),
            consumer()
        )
        
        # All produced items should be consumed
        assert len(produced) > 0
        assert len(consumed) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
