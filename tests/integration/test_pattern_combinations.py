"""
Integration tests for combining multiple resilience patterns
"""

import pytest
import asyncio
from aioresilience import (
    CircuitBreaker,
    RetryPolicy,
    FallbackHandler,
    Bulkhead,
    TimeoutManager,
)


class TestPatternStacking:
    """Test stacking multiple resilience patterns"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_retry(self):
        """Test circuit breaker combined with retry"""
        circuit = CircuitBreaker(name="test", failure_threshold=3)
        retry = RetryPolicy(max_attempts=3)
        
        call_count = 0
        
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Temporary error")
            return "success"
        
        # Should retry and succeed
        async def retry_with_circuit():
            return await circuit.call(flaky_function)
        
        result = await retry.execute(retry_with_circuit)
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_with_fallback(self):
        """Test circuit breaker with fallback"""
        circuit = CircuitBreaker(name="test", failure_threshold=2)
        fallback = FallbackHandler(fallback="fallback_data")
        
        async def failing_function():
            raise ValueError("Service error")
        
        # Fail enough times to open circuit
        for _ in range(2):
            try:
                await circuit.call(failing_function)
            except:
                pass
        
        # Circuit should be open, fallback should activate
        async def fallback_with_circuit():
            return await circuit.call(failing_function)
        
        result = await fallback.execute(fallback_with_circuit)
        assert result == "fallback_data"
    
    @pytest.mark.asyncio
    async def test_retry_with_fallback(self):
        """Test retry with fallback when all retries fail"""
        retry = RetryPolicy(max_attempts=3, initial_delay=0.01)
        fallback = FallbackHandler(fallback="fallback")
        
        attempt_count = 0
        
        async def always_fails():
            nonlocal attempt_count
            attempt_count += 1
            raise ValueError("Always fails")
        
        async def retry_always_fails():
            return await retry.execute(always_fails)
        
        result = await fallback.execute(retry_always_fails)
        
        assert result == "fallback"
        assert attempt_count == 3  # All retries attempted
    
    @pytest.mark.asyncio
    async def test_triple_stack_circuit_retry_fallback(self):
        """Test circuit breaker + retry + fallback stack"""
        circuit = CircuitBreaker(name="test", failure_threshold=5)
        retry = RetryPolicy(max_attempts=2, initial_delay=0.01)
        fallback = FallbackHandler(fallback="fallback")
        
        call_count = 0
        
        async def intermittent_failure():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise ValueError("Failing")
            return "success"
        
        # Should fail twice, then use fallback
        async def call_with_circuit():
            return await circuit.call(intermittent_failure)
        
        async def execute_all():
            return await retry.execute(call_with_circuit)
        
        result = await fallback.execute(execute_all)
        
        assert result == "fallback"  # Retries exhausted, uses fallback
        assert call_count == 2  # 2 attempts (max_attempts)
    
    @pytest.mark.asyncio
    async def test_bulkhead_with_timeout(self):
        """Test bulkhead with timeout"""
        bulkhead = Bulkhead(max_concurrent=2)
        timeout_mgr = TimeoutManager(timeout=0.1)
        
        async def slow_operation():
            await asyncio.sleep(0.05)
            return "done"
        
        # Should complete within timeout
        async def execute_with_bulkhead():
            return await bulkhead.execute(slow_operation)
        
        result = await timeout_mgr.execute(execute_with_bulkhead)
        assert result == "done"
    
    @pytest.mark.asyncio
    async def test_bulkhead_rejects_with_circuit_breaker(self):
        """Test bulkhead rejection with circuit breaker"""
        bulkhead = Bulkhead(max_concurrent=1, max_waiting=0)
        circuit = CircuitBreaker(name="test", failure_threshold=3)
        
        async def operation():
            await asyncio.sleep(0.1)
            return "done"
        
        # Start one operation (fills bulkhead)
        task1 = asyncio.create_task(bulkhead.execute(operation))
        await asyncio.sleep(0.01)  # Let it acquire
        
        # Second should be rejected by bulkhead
        with pytest.raises(Exception):
            async def operation_with_bulkhead():
                return await bulkhead.execute(operation)
            await circuit.call(operation_with_bulkhead)
        
        await task1


class TestPatternInteractions:
    """Test how patterns interact with each other"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_preserves_retry_count(self):
        """Test circuit breaker doesn't interfere with retry counting"""
        circuit = CircuitBreaker(name="test", failure_threshold=10)
        retry = RetryPolicy(max_attempts=3)
        
        attempts = []
        
        async def track_attempts():
            attempts.append(1)
            raise ValueError("Error")
        
        async def call_with_circuit():
            return await circuit.call(track_attempts)
        
        try:
            await retry.execute(call_with_circuit)
        except ValueError:
            pass
        
        assert len(attempts) == 3
        metrics = circuit.get_metrics()
        assert metrics["failed_requests"] == 3
    
    @pytest.mark.asyncio
    async def test_fallback_chain_with_circuit_breakers(self):
        """Test fallback chain where each fallback has circuit breaker"""
        primary_circuit = CircuitBreaker(name="primary", failure_threshold=2)
        fallback_circuit = CircuitBreaker(name="fallback", failure_threshold=2)
        
        async def primary():
            raise ValueError("Primary failed")
        
        async def fallback_func():
            return "fallback_success"
        
        async def fallback_callable():
            return await fallback_circuit.call(fallback_func)
        
        fallback = FallbackHandler(fallback=fallback_callable)
        
        async def execute_primary():
            return await primary_circuit.call(primary)
        
        result = await fallback.execute(execute_primary)
        assert result == "fallback_success"
    
    @pytest.mark.asyncio
    async def test_concurrent_patterns_isolation(self):
        """Test patterns don't interfere when used concurrently"""
        circuit1 = CircuitBreaker(name="service1", failure_threshold=3)
        circuit2 = CircuitBreaker(name="service2", failure_threshold=3)
        
        async def service1():
            raise ValueError("Service 1 error")
        
        async def service2():
            return "service 2 ok"
        
        # Service 1 fails
        for _ in range(3):
            try:
                await circuit1.call(service1)
            except:
                pass
        
        # Service 2 should still work
        result = await circuit2.call(service2)
        assert result == "service 2 ok"
        from aioresilience.circuit_breaker import CircuitState
        assert circuit1.get_state() == CircuitState.OPEN
        assert circuit2.get_state() == CircuitState.CLOSED


class TestEndToEndScenarios:
    """End-to-end integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_api_with_full_resilience(self):
        """Test API call with full resilience stack"""
        circuit = CircuitBreaker(name="api", failure_threshold=3)
        retry = RetryPolicy(max_attempts=3, initial_delay=0.01)
        timeout_mgr = TimeoutManager(timeout=1.0)
        fallback = FallbackHandler(fallback={"data": [], "status": "degraded"})
        
        call_count = 0
        
        async def api_call():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("Network error")
            elif call_count == 2:
                await asyncio.sleep(0.02)
                return {"data": ["item1", "item2"], "status": "ok"}
            else:
                raise ValueError("Should not reach here")
        
        # Full stack: timeout -> retry -> circuit -> fallback
        async def call_with_circuit():
            return await circuit.call(api_call)
        
        async def call_with_timeout():
            return await timeout_mgr.execute(call_with_circuit)
        
        async def call_with_retry():
            return await retry.execute(call_with_timeout)
        
        result = await fallback.execute(call_with_retry)
        
        assert result["status"] == "ok"
        assert len(result["data"]) == 2
    
    @pytest.mark.asyncio
    async def test_gradual_degradation(self):
        """Test gradual degradation through fallback tiers"""
        circuit = CircuitBreaker(name="primary", failure_threshold=2)
        
        async def primary_service():
            raise ValueError("Primary down")
        
        async def cache_fallback():
            return {"data": "cached", "tier": "cache"}
        
        async def static_fallback():
            return {"data": "static", "tier": "static"}
        
        # Primary fails -> cache -> success
        fallback1 = FallbackHandler(fallback=cache_fallback)
        async def execute_with_circuit():
            return await circuit.call(primary_service)
        
        result = await fallback1.execute(execute_with_circuit)
        
        assert result["tier"] == "cache"
    
    @pytest.mark.asyncio
    async def test_high_concurrency_with_multiple_patterns(self):
        """Test multiple patterns under high concurrency"""
        circuit = CircuitBreaker(name="test", failure_threshold=100)  # High threshold to avoid opening
        bulkhead = Bulkhead(max_concurrent=20)  # Higher concurrency
        retry = RetryPolicy(max_attempts=2, initial_delay=0.001)
        
        success_count = 0
        fail_count = 0
        
        async def operation(should_fail):
            await asyncio.sleep(0.001)
            if should_fail:
                raise ValueError("Intentional failure")
            return "success"
        
        async def worker(i):
            nonlocal success_count, fail_count
            try:
                should_fail = (i % 10 == 0)  # 10% failure rate
                async def execute_chain():
                    async def with_bulkhead():
                        return await operation(should_fail)
                    async def with_circuit():
                        return await bulkhead.execute(with_bulkhead)
                    return await circuit.call(with_circuit)
                
                await retry.execute(execute_chain)
                success_count += 1
            except:
                fail_count += 1
        
        # Run 100 concurrent operations
        await asyncio.gather(*[worker(i) for i in range(100)], return_exceptions=True)
        
        # Some should succeed (failures get retried)
        # Note: With 10% failure rate and concurrent bulkhead limits, expect ~30-40% success
        assert success_count > 20  # At least 20% succeed
        from aioresilience.circuit_breaker import CircuitState
        # Circuit might open briefly but shouldn't stay open
        assert circuit.get_state() in [CircuitState.CLOSED, CircuitState.HALF_OPEN]
