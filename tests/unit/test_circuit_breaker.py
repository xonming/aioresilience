"""
Tests for Circuit Breaker implementation
"""
import pytest
import asyncio
from aioresilience import (
    CircuitBreaker,
    CircuitState,
    CircuitBreakerOpenError,
    CircuitConfig,
    circuit_breaker,
    get_circuit_breaker,
    get_all_circuit_metrics,
)


class TestCircuitBreaker:
    """Test CircuitBreaker basic functionality"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_initialization(self):
        """Test circuit breaker initializes with correct defaults"""
        cb = CircuitBreaker(name="test")
        
        assert cb.name == "test"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60.0
        assert cb.success_threshold == 2
        assert cb.metrics.total_requests == 0

    @pytest.mark.asyncio
    async def test_circuit_closed_allows_execution(self):
        """Test that CLOSED circuit allows execution"""
        cb = CircuitBreaker(name="test", config=CircuitConfig(failure_threshold=3))
        
        assert await cb.can_execute() is True
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_circuit_opens_after_threshold(self):
        """Test circuit opens after failure threshold"""
        cb = CircuitBreaker(name="test", config=CircuitConfig(failure_threshold=3))
        
        # Trigger failures
        for i in range(3):
            await cb.on_failure()
        
        assert cb.state == CircuitState.OPEN
        assert cb.metrics.consecutive_failures == 3
        assert await cb.can_execute() is False

    @pytest.mark.asyncio
    async def test_circuit_half_open_transition(self):
        """Test transition from OPEN to HALF_OPEN after timeout"""
        cb = CircuitBreaker(
            name="test",
            config=CircuitConfig(
                failure_threshold=2,
                recovery_timeout=0.1  # 100ms timeout for testing
            )
        )
        
        # Open the circuit
        await cb.on_failure()
        await cb.on_failure()
        assert cb.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Should transition to HALF_OPEN
        can_exec = await cb.can_execute()
        assert can_exec is True
        assert cb.state == CircuitState.HALF_OPEN

    @pytest.mark.asyncio
    async def test_circuit_closes_after_success_threshold(self):
        """Test circuit closes after success threshold in HALF_OPEN"""
        cb = CircuitBreaker(
            name="test",
            config=CircuitConfig(
                failure_threshold=2,
                recovery_timeout=0.1,
                success_threshold=2
            )
        )
        
        # Open the circuit
        await cb.on_failure()
        await cb.on_failure()
        assert cb.state == CircuitState.OPEN
        
        # Wait and transition to HALF_OPEN
        await asyncio.sleep(0.15)
        await cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN
        
        # Record successes to close
        await cb.on_success()
        await cb.on_success()
        
        assert cb.state == CircuitState.CLOSED
        assert cb.metrics.consecutive_successes == 2

    @pytest.mark.asyncio
    async def test_circuit_reopens_on_half_open_failure(self):
        """Test circuit reopens on failure in HALF_OPEN state"""
        cb = CircuitBreaker(
            name="test",
            config=CircuitConfig(
                failure_threshold=2,
                recovery_timeout=0.1
            )
        )
        
        # Open the circuit
        await cb.on_failure()
        await cb.on_failure()
        
        # Wait and transition to HALF_OPEN
        await asyncio.sleep(0.15)
        await cb.can_execute()
        assert cb.state == CircuitState.HALF_OPEN
        
        # Failure in HALF_OPEN should reopen
        await cb.on_failure()
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_call_success(self):
        """Test successful circuit breaker call"""
        cb = CircuitBreaker(name="test")
        
        async def successful_func():
            return "success"
        
        result = await cb.call(successful_func)
        
        assert result == "success"
        assert cb.metrics.successful_requests == 1
        assert cb.metrics.total_requests == 1

    @pytest.mark.asyncio
    async def test_circuit_call_failure(self):
        """Test failed circuit breaker call"""
        cb = CircuitBreaker(name="test", config=CircuitConfig(failure_threshold=3))
        
        async def failing_func():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            await cb.call(failing_func)
        
        assert cb.metrics.failed_requests == 1
        assert cb.metrics.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_circuit_call_when_open(self):
        """Test call fails fast when circuit is OPEN"""
        cb = CircuitBreaker(name="test", config=CircuitConfig(failure_threshold=2))
        
        # Open the circuit
        await cb.on_failure()
        await cb.on_failure()
        
        async def dummy_func():
            return "should not execute"
        
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(dummy_func)

    @pytest.mark.asyncio
    async def test_circuit_timeout(self):
        """Test circuit breaker with timeout"""
        cb = CircuitBreaker(name="test", config=CircuitConfig(timeout=0.1, failure_threshold=3))
        
        async def slow_func():
            await asyncio.sleep(1.0)
            return "too slow"
        
        with pytest.raises(asyncio.TimeoutError):
            await cb.call(slow_func)
        
        assert cb.metrics.failed_requests == 1

    @pytest.mark.asyncio
    async def test_circuit_metrics(self):
        """Test circuit breaker metrics"""
        cb = CircuitBreaker(name="test")
        
        await cb.on_success()
        await cb.on_success()
        await cb.on_failure()
        
        metrics = cb.get_metrics()
        
        assert metrics["name"] == "test"
        assert metrics["total_requests"] == 3
        assert metrics["successful_requests"] == 2
        assert metrics["failed_requests"] == 1
        assert metrics["failure_rate"] == pytest.approx(1/3)

    @pytest.mark.asyncio
    async def test_circuit_reset(self):
        """Test manual circuit reset"""
        cb = CircuitBreaker(name="test", config=CircuitConfig(failure_threshold=2))
        
        # Open the circuit
        await cb.on_failure()
        await cb.on_failure()
        assert cb.state == CircuitState.OPEN
        
        # Reset
        await cb.reset()
        
        assert cb.state == CircuitState.CLOSED
        assert cb.metrics.total_requests == 0
        assert cb.metrics.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_half_open_calls_counter(self):
        """Test that half_open_calls counter is properly managed"""
        cb = CircuitBreaker(
            name="test",
            config=CircuitConfig(
                failure_threshold=1,
                recovery_timeout=0.1,
                half_open_max_calls=2
            )
        )
        
        # Open circuit
        await cb.on_failure()
        await asyncio.sleep(0.15)
        
        # Transition to half-open
        assert await cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.half_open_calls == 0  # Reset on transition
        
        # Simulate tracking calls
        async with cb._lock:
            cb.half_open_calls = 1
        
        assert await cb.can_execute() is True  # Still under limit
        
        async with cb._lock:
            cb.half_open_calls = 2
        
        assert await cb.can_execute() is False  # At limit


class TestCircuitBreakerDecorator:
    """Test circuit_breaker decorator"""

    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator usage"""
        call_count = 0
        
        @circuit_breaker("test", failure_threshold=3)
        async def test_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await test_func()
        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_decorator_with_failures(self):
        """Test decorator with failures"""
        
        @circuit_breaker("test", failure_threshold=2)
        async def failing_func():
            raise ValueError("Test error")
        
        # First two calls should raise ValueError
        for _ in range(2):
            with pytest.raises(ValueError):
                await failing_func()
        
        # Third call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            await failing_func()

    @pytest.mark.asyncio
    async def test_decorator_exposes_circuit_breaker(self):
        """Test that decorator exposes circuit breaker instance"""
        
        @circuit_breaker("test", failure_threshold=5)
        async def test_func():
            return "success"
        
        assert hasattr(test_func, 'circuit_breaker')
        assert isinstance(test_func.circuit_breaker, CircuitBreaker)
        assert test_func.circuit_breaker.name == "test"


class TestCircuitBreakerManager:
    """Test global circuit breaker manager"""

    @pytest.mark.asyncio
    async def test_get_circuit_breaker(self):
        """Test getting circuit breaker from global manager"""
        cb1 = get_circuit_breaker("backend", failure_threshold=3)
        cb2 = get_circuit_breaker("backend")
        
        # Should return the same instance
        assert cb1 is cb2
        assert cb1.name == "backend"

    @pytest.mark.asyncio
    async def test_get_all_circuit_metrics(self):
        """Test getting all circuit metrics"""
        # Create some circuit breakers
        cb1 = get_circuit_breaker("service1", failure_threshold=3)
        cb2 = get_circuit_breaker("service2", failure_threshold=5)
        
        await cb1.on_success()
        await cb2.on_failure()
        
        metrics = get_all_circuit_metrics()
        
        assert "service1" in metrics
        assert "service2" in metrics
        assert metrics["service1"]["successful_requests"] == 1
        assert metrics["service2"]["failed_requests"] == 1


class TestCircuitBreakerThreadSafety:
    """Test circuit breaker thread safety with concurrent access"""

    @pytest.mark.asyncio
    async def test_concurrent_can_execute(self):
        """Test concurrent can_execute calls are thread-safe"""
        cb = CircuitBreaker(name="test", config=CircuitConfig(failure_threshold=10))
        
        # Multiple concurrent can_execute calls
        results = await asyncio.gather(*[
            cb.can_execute() for _ in range(100)
        ])
        
        assert all(results)  # All should return True
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_concurrent_failures(self):
        """Test concurrent failure tracking is thread-safe"""
        cb = CircuitBreaker(name="test", config=CircuitConfig(failure_threshold=50))
        
        # Record 50 concurrent failures
        await asyncio.gather(*[
            cb.on_failure() for _ in range(50)
        ])
        
        # Should have exactly 50 failures
        assert cb.metrics.failed_requests == 50
        assert cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_concurrent_successes(self):
        """Test concurrent success tracking is thread-safe"""
        cb = CircuitBreaker(name="test")
        
        # Record 100 concurrent successes
        await asyncio.gather(*[
            cb.on_success() for _ in range(100)
        ])
        
        # Should have exactly 100 successes
        assert cb.metrics.successful_requests == 100
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_concurrent_state_transitions(self):
        """Test that concurrent operations don't corrupt state"""
        cb = CircuitBreaker(name="test", config=CircuitConfig(failure_threshold=10, recovery_timeout=0.1))
        
        async def mixed_operations():
            """Mix of operations"""
            for _ in range(5):
                await cb.on_success()
                await cb.on_failure()
                await cb.can_execute()
        
        # Run multiple tasks concurrently
        await asyncio.gather(*[
            mixed_operations() for _ in range(10)
        ])
        
        # Verify metrics are consistent
        metrics = cb.get_metrics()
        assert metrics["total_requests"] == metrics["successful_requests"] + metrics["failed_requests"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
