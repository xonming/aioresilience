"""
Integration tests for event emission across all patterns
"""

import pytest
import asyncio
from aioresilience import (
    CircuitBreaker, RetryPolicy, TimeoutManager, FallbackHandler,
    Bulkhead, BasicLoadShedder, LocalRateLimiter,
    AdaptiveConcurrencyLimiter, BackpressureManager,
    CircuitConfig, RetryConfig, TimeoutConfig, BulkheadConfig,
    LoadSheddingConfig, BackpressureConfig, FallbackConfig, AdaptiveConcurrencyConfig
)
from aioresilience.events import global_bus, EventType, PatternType


async def failing_operation():
    """Simulated failing operation"""
    raise ValueError("Test failure")


async def successful_operation():
    """Simulated successful operation"""
    await asyncio.sleep(0.01)
    return "success"


class TestRetryEvents:
    """Test retry event emission"""
    
    def setup_method(self):
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_retry_emits_attempt_and_success_events(self):
        """Test retry emits attempt and success events"""
        retry = RetryPolicy(config=RetryConfig(max_attempts=3, initial_delay=0.01))
        
        events = []
        
        @retry.events.on("*")
        async def capture(event):
            events.append(event)
        
        # Execute with one failure then success
        call_count = 0
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Fail once")
            return "success"
        
        result = await retry.execute(flaky_operation)
        
        assert result == "success"
        assert len(events) >= 2  # At least retry_attempt and retry_success
        assert any(e.event_type == EventType.RETRY_ATTEMPT for e in events)
        assert any(e.event_type == EventType.RETRY_SUCCESS for e in events)
    
    @pytest.mark.asyncio
    async def test_retry_emits_exhausted_event(self):
        """Test retry emits exhausted event when all attempts fail"""
        retry = RetryPolicy(config=RetryConfig(max_attempts=2, initial_delay=0.01))
        
        exhausted_events = []
        
        @retry.events.on(EventType.RETRY_EXHAUSTED.value)
        async def capture(event):
            exhausted_events.append(event)
        
        try:
            await retry.execute(failing_operation)
        except ValueError:
            pass
        
        assert len(exhausted_events) == 1
        assert exhausted_events[0].event_type == EventType.RETRY_EXHAUSTED


class TestTimeoutEvents:
    """Test timeout event emission"""
    
    def setup_method(self):
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_timeout_emits_success_event(self):
        """Test timeout emits success event"""
        timeout_mgr = TimeoutManager(config=TimeoutConfig(timeout=1.0))
        
        success_events = []
        
        @timeout_mgr.events.on(EventType.TIMEOUT_SUCCESS.value)
        async def capture(event):
            success_events.append(event)
        
        result = await timeout_mgr.execute(successful_operation)
        
        assert result == "success"
        assert len(success_events) == 1
        assert success_events[0].event_type == EventType.TIMEOUT_SUCCESS
    
    @pytest.mark.asyncio
    async def test_timeout_emits_occurred_event(self):
        """Test timeout emits occurred event"""
        timeout_mgr = TimeoutManager(config=TimeoutConfig(timeout=0.01, raise_on_timeout=False))
        
        timeout_events = []
        
        @timeout_mgr.events.on(EventType.TIMEOUT_OCCURRED.value)
        async def capture(event):
            timeout_events.append(event)
        
        async def slow_operation():
            await asyncio.sleep(1.0)
        
        result = await timeout_mgr.execute(slow_operation)
        
        assert result is None
        assert len(timeout_events) == 1
        assert timeout_events[0].event_type == EventType.TIMEOUT_OCCURRED


class TestFallbackEvents:
    """Test fallback event emission"""
    
    def setup_method(self):
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_fallback_emits_primary_failed_and_fallback_executed(self):
        """Test fallback emits appropriate events"""
        fallback = FallbackHandler(config=FallbackConfig(fallback="fallback_value"))
        
        events = []
        
        @fallback.events.on("*")
        async def capture(event):
            events.append(event)
        
        result = await fallback.execute(failing_operation)
        
        assert result == "fallback_value"
        assert len(events) == 2
        assert events[0].event_type == EventType.PRIMARY_FAILED
        assert events[1].event_type == EventType.FALLBACK_EXECUTED


class TestBulkheadEvents:
    """Test bulkhead event emission"""
    
    def setup_method(self):
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_bulkhead_emits_acquired_and_released(self):
        """Test bulkhead emits slot acquired and released events"""
        bulkhead = Bulkhead(name="test-bulkhead", config=BulkheadConfig(max_concurrent=2))
        
        events = []
        
        @bulkhead.events.on("*")
        async def capture(event):
            events.append(event)
        
        await bulkhead.execute(successful_operation)
        
        assert len(events) == 2
        assert events[0].event_type == EventType.SLOT_ACQUIRED
        assert events[1].event_type == EventType.SLOT_RELEASED
    
    @pytest.mark.asyncio
    async def test_bulkhead_emits_full_event(self):
        """Test bulkhead emits full event when at capacity"""
        bulkhead = Bulkhead(name="test-bulkhead", config=BulkheadConfig(max_concurrent=1, max_waiting=0))
        
        full_events = []
        
        @bulkhead.events.on(EventType.BULKHEAD_FULL.value)
        async def capture(event):
            full_events.append(event)
        
        # Fill the bulkhead
        async def long_operation():
            await asyncio.sleep(0.1)
        
        # Start one operation
        task = asyncio.create_task(bulkhead.execute(long_operation))
        await asyncio.sleep(0.01)  # Give it time to acquire
        
        # Try another (should be rejected)
        from aioresilience import BulkheadFullError
        with pytest.raises(BulkheadFullError):
            await bulkhead.execute(successful_operation)
        
        await task
        
        assert len(full_events) == 1
        assert full_events[0].event_type == EventType.BULKHEAD_FULL


class TestLoadShedderEvents:
    """Test load shedder event emission"""
    
    def setup_method(self):
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_load_shedder_emits_accepted_event(self):
        """Test load shedder emits request accepted event"""
        shedder = BasicLoadShedder(config=LoadSheddingConfig(max_requests=10))
        
        accepted_events = []
        
        @shedder.events.on(EventType.REQUEST_ACCEPTED.value)
        async def capture(event):
            accepted_events.append(event)
        
        acquired = await shedder.acquire()
        assert acquired
        await shedder.release()
        
        assert len(accepted_events) == 1
        assert accepted_events[0].event_type == EventType.REQUEST_ACCEPTED
    
    @pytest.mark.asyncio
    async def test_load_shedder_emits_shed_event(self):
        """Test load shedder emits request shed event"""
        shedder = BasicLoadShedder(config=LoadSheddingConfig(max_requests=1))
        
        shed_events = []
        
        @shedder.events.on(EventType.REQUEST_SHED.value)
        async def capture(event):
            shed_events.append(event)
        
        # Fill capacity
        await shedder.acquire()
        
        # Try to acquire again (should shed)
        acquired = await shedder.acquire()
        assert not acquired
        
        assert len(shed_events) == 1
        assert shed_events[0].event_type == EventType.REQUEST_SHED


class TestRateLimiterEvents:
    """Test rate limiter event emission"""
    
    def setup_method(self):
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_rate_limiter_emits_allowed_event(self):
        """Test rate limiter emits request allowed event"""
        limiter = LocalRateLimiter()
        
        allowed_events = []
        
        @limiter.events.on(EventType.REQUEST_ALLOWED.value)
        async def capture(event):
            allowed_events.append(event)
        
        result = await limiter.check_rate_limit("user1", "10/second")
        
        assert result is True
        assert len(allowed_events) == 1
        assert allowed_events[0].event_type == EventType.REQUEST_ALLOWED
    
    @pytest.mark.asyncio
    async def test_rate_limiter_emits_rejected_event(self):
        """Test rate limiter emits request rejected event"""
        limiter = LocalRateLimiter()
        
        rejected_events = []
        
        @limiter.events.on(EventType.REQUEST_REJECTED.value)
        async def capture(event):
            rejected_events.append(event)
        
        # Exhaust rate limit
        for _ in range(10):
            await limiter.check_rate_limit("user1", "10/second")
        
        # This should be rejected
        result = await limiter.check_rate_limit("user1", "10/second")
        
        assert result is False
        assert len(rejected_events) >= 1
        assert rejected_events[-1].event_type == EventType.REQUEST_REJECTED


class TestAdaptiveConcurrencyEvents:
    """Test adaptive concurrency limiter event emission"""
    
    def setup_method(self):
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_adaptive_limiter_emits_load_level_change(self):
        """Test adaptive limiter emits load level change events"""
        config = AdaptiveConcurrencyConfig(
            initial_limit=10,
            measurement_window=5
        )
        limiter = AdaptiveConcurrencyLimiter("test", config)
        
        level_change_events = []
        
        @limiter.events.on(EventType.LOAD_LEVEL_CHANGE.value)
        async def capture(event):
            level_change_events.append(event)
        
        # Generate high success rate to trigger increase
        for _ in range(5):
            await limiter.acquire()
            await limiter.release(success=True)
        
        # Should have emitted at least one load level change
        assert len(level_change_events) >= 1
        assert level_change_events[0].event_type == EventType.LOAD_LEVEL_CHANGE


class TestBackpressureEvents:
    """Test backpressure manager event emission"""
    
    def setup_method(self):
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_backpressure_emits_threshold_exceeded(self):
        """Test backpressure emits threshold exceeded event"""
        backpressure = BackpressureManager(
            config=BackpressureConfig(
                max_pending=100,
                high_water_mark=10,
                low_water_mark=5
            )
        )
        
        threshold_events = []
        
        @backpressure.events.on(EventType.THRESHOLD_EXCEEDED.value)
        async def capture(event):
            threshold_events.append(event)
        
        # Acquire up to high water mark + 1 (should trigger threshold exceeded)
        for i in range(11):
            # Use timeout to avoid blocking if backpressure activates
            result = await backpressure.acquire(timeout=0.1)
            if not result:
                break
        
        # Release all
        for _ in range(backpressure.pending_count):
            await backpressure.release()
        
        assert len(threshold_events) == 1
        assert threshold_events[0].event_type == EventType.THRESHOLD_EXCEEDED
    
    @pytest.mark.asyncio
    async def test_backpressure_emits_load_level_change(self):
        """Test backpressure emits load level change when deactivating"""
        backpressure = BackpressureManager(
            config=BackpressureConfig(
                max_pending=100,
                high_water_mark=10,
                low_water_mark=5
            )
        )
        
        level_change_events = []
        
        @backpressure.events.on(EventType.LOAD_LEVEL_CHANGE.value)
        async def capture(event):
            level_change_events.append(event)
        
        # Activate backpressure by acquiring up to high water mark
        for _ in range(11):
            result = await backpressure.acquire(timeout=0.1)
            if not result:
                break
        
        # Release to deactivate (must go below low water mark = 5)
        # We have 11, need to release 7 to get to 4 (below 5)
        for _ in range(7):
            await backpressure.release()
        
        # Clean up remaining
        remaining = backpressure.pending_count
        for _ in range(remaining):
            await backpressure.release()
        
        assert len(level_change_events) == 1
        assert level_change_events[0].event_type == EventType.LOAD_LEVEL_CHANGE


class TestGlobalBusIntegration:
    """Test global bus receives events from all patterns"""
    
    def setup_method(self):
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_global_bus_receives_events_from_multiple_patterns(self):
        """Test global bus receives events from all patterns"""
        all_events = []
        
        @global_bus.on("*")
        async def capture_all(event):
            all_events.append(event)
        
        # Create multiple patterns and trigger events
        circuit = CircuitBreaker(name="test-circuit", config=CircuitConfig(failure_threshold=2))
        retry = RetryPolicy(config=RetryConfig(max_attempts=2, initial_delay=0.01))
        timeout_mgr = TimeoutManager(config=TimeoutConfig(timeout=1.0))
        
        # Trigger events
        await circuit.call(successful_operation)
        
        try:
            await retry.execute(failing_operation)
        except:
            pass
        
        await timeout_mgr.execute(successful_operation)
        
        # Should have events from all patterns
        assert len(all_events) > 0
        pattern_types = {e.pattern_type.value for e in all_events}
        assert PatternType.CIRCUIT_BREAKER.value in pattern_types
        assert PatternType.RETRY.value in pattern_types
        assert PatternType.TIMEOUT.value in pattern_types
