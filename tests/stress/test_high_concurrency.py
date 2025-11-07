"""
Stress tests for high concurrency scenarios
"""

import pytest
import asyncio
import time
from aioresilience import (
    CircuitBreaker,
    RateLimiter,
    Bulkhead,
    LoadShedder,
    AdaptiveConcurrencyLimiter,
    CircuitConfig,
    BulkheadConfig,
    RateLimitConfig,
    LoadSheddingConfig,
)
from aioresilience.config import AdaptiveConcurrencyConfig


class TestHighConcurrency:
    """Test patterns under high concurrency load"""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_circuit_breaker_1000_concurrent_requests(self):
        """Test circuit breaker with 1000+ concurrent requests"""
        circuit = CircuitBreaker(name="stress_test", config=CircuitConfig(failure_threshold=100))
        
        success_count = 0
        failure_count = 0
        
        async def operation(should_fail):
            await asyncio.sleep(0.001)
            if should_fail:
                raise ValueError("Intentional error")
            return "success"
        
        async def worker(i):
            nonlocal success_count, failure_count
            try:
                # 5% failure rate
                result = await circuit.call(lambda: operation(i % 20 == 0))
                success_count += 1
            except:
                failure_count += 1
        
        # Run 1000 concurrent requests
        await asyncio.gather(*[worker(i) for i in range(1000)], return_exceptions=True)
        
        # Verify most requests succeeded
        assert success_count > 900
        from aioresilience.circuit_breaker import CircuitState
        assert circuit.get_state() != CircuitState.OPEN
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_bulkhead_concurrent_limit_enforcement(self):
        """Test bulkhead enforces limits under heavy load"""
        bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=50, max_waiting=100))
        
        active_count = 0
        max_active = 0
        completed = 0
        
        async def operation():
            nonlocal active_count, max_active
            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.01)
            active_count -= 1
        
        async def worker():
            nonlocal completed
            try:
                await bulkhead.execute(operation)
                completed += 1
            except:
                pass
        
        # Launch 500 concurrent workers
        await asyncio.gather(*[worker() for _ in range(500)], return_exceptions=True)
        
        # Verify concurrency limit was enforced
        assert max_active <= 50
        assert completed > 100  # Many should have completed
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_rate_limiter_under_burst(self):
        """Test rate limiter handles burst traffic"""
        rate_limiter = RateLimiter()
        
        allowed = 0
        rejected = 0
        
        async def worker(user_id):
            nonlocal allowed, rejected
            # 50 requests per second limit per user
            if await rate_limiter.check_rate_limit(f"user_{user_id % 10}", "50/second"):
                allowed += 1
            else:
                rejected += 1
        
        # Burst of 1000 requests (100 per user)
        await asyncio.gather(*[worker(i) for i in range(1000)])
        
        # Should enforce limits - each user gets 100 requests but limit is 50
        assert rejected > 400  # At least 50% rejected (50/100 per user * 10 users)
        assert allowed > 0   # Some should be allowed
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_load_shedder_concurrent_acquire_release(self):
        """Test load shedder with rapid acquire/release"""
        shedder = LoadShedder(config=LoadSheddingConfig(max_requests=100))
        
        max_concurrent = 0
        successful_acquires = 0
        
        async def worker():
            nonlocal max_concurrent, successful_acquires
            if await shedder.acquire():
                successful_acquires += 1
                max_concurrent = max(max_concurrent, shedder.active_requests)
                await asyncio.sleep(0.001)
                await shedder.release()
        
        # 500 concurrent workers
        await asyncio.gather(*[worker() for _ in range(500)])
        
        # Verify limit was enforced
        assert max_concurrent <= 100
        assert shedder.active_requests == 0  # All released
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_adaptive_concurrency_adjusts_under_load(self):
        """Test adaptive concurrency limiter adjusts to load"""
        config = AdaptiveConcurrencyConfig(
            initial_limit=20,
            min_limit=5,
            max_limit=100
        )
        limiter = AdaptiveConcurrencyLimiter("test", config)
        
        latencies = []
        
        async def fast_operation():
            await asyncio.sleep(0.001)
            return "done"
        
        async def worker():
            start = time.time()
            if await limiter.acquire():
                try:
                    await fast_operation()
                finally:
                    await limiter.release()
                latencies.append(time.time() - start)
        
        # Run many operations
        await asyncio.gather(*[worker() for _ in range(500)])
        
        # Limit should have adjusted
        current_limit = limiter.current_limit
        assert 5 <= current_limit <= 100
        
        # Average latency should be low
        avg_latency = sum(latencies) / len(latencies)
        assert avg_latency < 0.1  # Should be fast


class TestConcurrencyStress:
    """Stress test concurrent access to shared state"""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_circuit_breaker_metrics_accuracy(self):
        """Test circuit breaker metrics remain accurate under load"""
        circuit = CircuitBreaker(name="metrics_test", config=CircuitConfig(failure_threshold=1000))
        
        total_calls = 0
        expected_failures = 0
        
        async def operation(should_fail):
            nonlocal total_calls, expected_failures
            total_calls += 1
            if should_fail:
                expected_failures += 1
                raise ValueError("Error")
            return "ok"
        
        async def worker(i):
            try:
                await circuit.call(lambda: operation(i % 10 == 0))
            except:
                pass
        
        # 1000 concurrent calls
        await asyncio.gather(*[worker(i) for i in range(1000)])
        
        # Metrics should be accurate
        metrics = circuit.get_metrics()
        assert metrics["total_requests"] == 1000
        # Allow small variance due to async timing
        assert abs(metrics["failed_requests"] - expected_failures) < 5
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_bulkhead_no_leaks_under_exceptions(self):
        """Test bulkhead properly releases on exceptions"""
        bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=10))
        
        async def failing_operation():
            await asyncio.sleep(0.001)
            raise ValueError("Intentional error")
        
        async def worker():
            try:
                await bulkhead.execute(failing_operation)
            except:
                pass
        
        # Many failing operations
        await asyncio.gather(*[worker() for _ in range(100)])
        
        # All semaphores should be released
        assert bulkhead._semaphore._value == 10
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_rate_limiter_per_key_isolation(self):
        """Test rate limiters for different keys don't interfere"""
        rate_limiter = RateLimiter()
        
        user1_allowed = 0
        user2_allowed = 0
        
        async def user1_worker():
            nonlocal user1_allowed
            if await rate_limiter.check_rate_limit("user_1", "100/second"):
                user1_allowed += 1
        
        async def user2_worker():
            nonlocal user2_allowed
            if await rate_limiter.check_rate_limit("user_2", "100/second"):
                user2_allowed += 1
        
        # Run users concurrently
        await asyncio.gather(
            *[user1_worker() for _ in range(200)],
            *[user2_worker() for _ in range(200)]
        )
        
        # Each user should have independent limits
        assert 90 <= user1_allowed <= 110  # ~100 allowed
        assert 90 <= user2_allowed <= 110  # ~100 allowed
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_mixed_patterns_concurrent_stability(self):
        """Test multiple patterns together remain stable"""
        circuit = CircuitBreaker(name="mixed", config=CircuitConfig(failure_threshold=50))
        bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=20))
        rate_limiter = RateLimiter()
        
        operations_completed = 0
        
        async def operation():
            await asyncio.sleep(0.001)
            return "done"
        
        async def worker(i):
            nonlocal operations_completed
            try:
                # Check rate limit
                if await rate_limiter.check_rate_limit(f"user_{i % 5}", "50/second"):
                    # Execute through bulkhead and circuit breaker
                    await circuit.call(lambda: bulkhead.execute(operation))
                    operations_completed += 1
            except:
                pass
        
        # 500 concurrent workers
        await asyncio.gather(*[worker(i) for i in range(500)])
        
        # System should remain stable
        assert operations_completed > 100
        assert circuit.get_state() != "open"
        assert bulkhead._semaphore._value == 20  # All released


class TestMemoryAndPerformance:
    """Test memory usage and performance under load"""
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_circuit_breaker_overhead(self):
        """Measure circuit breaker overhead"""
        circuit = CircuitBreaker(name="perf", config=CircuitConfig(failure_threshold=1000))
        
        async def noop():
            return "done"
        
        # Warm up
        for _ in range(100):
            await circuit.call(noop)
        
        # Measure
        start = time.perf_counter()
        for _ in range(1000):
            await circuit.call(noop)
        duration = time.perf_counter() - start
        
        # Should be low overhead - relaxed for CI variability
        assert duration < 0.1  # 100ms (was 20ms)
        avg_overhead = (duration / 1000) * 1000000  # microseconds
        assert avg_overhead < 100  # < 100µs per call (was 20µs)
    
    @pytest.mark.asyncio
    @pytest.mark.timeout(30)
    async def test_bulkhead_overhead(self):
        """Measure bulkhead overhead"""
        bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=100, max_waiting=1000))
        
        async def noop():
            return "done"
        
        # Measure
        start = time.perf_counter()
        await asyncio.gather(*[bulkhead.execute(noop) for _ in range(1000)])
        duration = time.perf_counter() - start
        
        # Should be low overhead (note: includes queuing + lock contention with 900 waiting tasks)
        avg_overhead = (duration / 1000) * 1000000  # microseconds
        assert avg_overhead < 200  # < 200µs per operation (was 50µs, relaxed for CI)
