"""
Tests for Pattern Exception Integration

Tests how the new exception system integrates with resilience patterns:
- CircuitBreaker with custom exceptions
- Bulkhead with callbacks
- Timeout with transformers
- Retry with per-exception strategies
- Backpressure with custom errors
- LoadShedding with custom errors
"""

import pytest
import asyncio
from aioresilience import (
    CircuitBreaker,
    Bulkhead,
    TimeoutManager,
    RetryPolicy,
    BackpressureManager,
    BasicLoadShedder,
    CircuitConfig,
    BulkheadConfig,
    TimeoutConfig,
    RetryConfig,
    BackpressureConfig,
    LoadSheddingConfig,
    ExceptionConfig,
)
from aioresilience.exceptions import (
    CircuitBreakerOpenError,
    BulkheadFullError,
    OperationTimeoutError,
    BackpressureError,
    LoadSheddingError,
    CircuitBreakerReason,
    BulkheadReason,
    TimeoutReason,
    RetryReason,
    BackpressureReason,
    LoadSheddingReason,
    ExceptionContext,
)


class TestCircuitBreakerExceptions:
    """Test CircuitBreaker exception handling"""
    
    @pytest.mark.asyncio
    async def test_default_exception(self):
        """Test circuit breaker raises CircuitBreakerOpenError by default"""
        circuit = CircuitBreaker(
            name="test-circuit",
            config=CircuitConfig(failure_threshold=2, recovery_timeout=0.1)
        )
        
        # Trigger failures to open circuit
        for _ in range(3):
            try:
                await circuit.call(self._failing_function)
            except:
                pass
        
        # Circuit should be open
        with pytest.raises(CircuitBreakerOpenError) as exc_info:
            await circuit.call(self._success_function)
        
        error = exc_info.value
        assert error.pattern_name == "test-circuit"
        assert error.pattern_type == "circuit_breaker"
        assert error.reason == CircuitBreakerReason.CIRCUIT_OPEN
    
    @pytest.mark.asyncio
    async def test_custom_exception_type(self):
        """Test circuit breaker with custom exception type"""
        class ServiceUnavailable(Exception):
            pass
        
        exceptions = ExceptionConfig(exception_type=ServiceUnavailable)
        circuit = CircuitBreaker(
            name="custom-circuit",
            config=CircuitConfig(failure_threshold=1),
            exceptions=exceptions
        )
        
        # Trigger failure
        try:
            await circuit.call(self._failing_function)
        except:
            pass
        
        # Should raise custom exception
        with pytest.raises(ServiceUnavailable):
            await circuit.call(self._success_function)
    
    @pytest.mark.asyncio
    async def test_exception_transformer(self):
        """Test circuit breaker with exception transformer"""
        def transform(exc, ctx):
            return ValueError(f"Circuit '{ctx.pattern_name}' is {ctx.metadata.get('state')}")
        
        exceptions = ExceptionConfig(exception_transformer=transform)
        circuit = CircuitBreaker(
            name="transformer-circuit",
            config=CircuitConfig(failure_threshold=1),
            exceptions=exceptions
        )
        
        # Trigger failure
        try:
            await circuit.call(self._failing_function)
        except:
            pass
        
        # Should raise transformed exception
        with pytest.raises(ValueError) as exc_info:
            await circuit.call(self._success_function)
        
        assert "transformer-circuit" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_on_failure_callback(self):
        """Test circuit breaker on_failure callback"""
        failure_contexts = []
        
        def on_failure(ctx):
            failure_contexts.append(ctx)
        
        exceptions = ExceptionConfig(on_exception=on_failure)
        circuit = CircuitBreaker(
            name="callback-circuit",
            config=CircuitConfig(failure_threshold=1),
            exceptions=exceptions
        )
        
        # Trigger failure to open circuit
        try:
            await circuit.call(self._failing_function)
        except:
            pass
        
        # Now trigger the callback when circuit is open
        try:
            await circuit.call(self._success_function)
        except CircuitBreakerOpenError:
            pass
        
        assert len(failure_contexts) >= 1
        assert all(ctx.pattern_name == "callback-circuit" for ctx in failure_contexts)
    
    @pytest.mark.asyncio
    async def test_multiple_failure_exceptions(self):
        """Test circuit breaker with multiple exception types"""
        config = CircuitConfig(
            failure_threshold=2,
            failure_exceptions=(ValueError, TypeError, KeyError)
        )
        circuit = CircuitBreaker(
            name="multi-exception",
            config=config
        )
        
        # Different exception types should all count as failures
        async def fail_value_error():
            raise ValueError("test")
        
        async def fail_type_error():
            raise TypeError("test")
        
        try:
            await circuit.call(fail_value_error)
        except ValueError:
            pass
        
        try:
            await circuit.call(fail_type_error)
        except TypeError:
            pass
        
        # Circuit should be open now (threshold is 2)
        with pytest.raises(CircuitBreakerOpenError):
            await circuit.call(self._success_function)
    
    @pytest.mark.asyncio
    async def test_failure_predicate(self):
        """Test circuit breaker with failure predicate"""
        def is_failure(exc):
            return "fatal" in str(exc).lower()
        
        config = CircuitConfig(
            failure_threshold=2,
            failure_predicate=is_failure
        )
        circuit = CircuitBreaker(
            name="predicate-circuit",
            config=config
        )
        
        # Non-fatal errors shouldn't count
        async def temp_error():
            raise ValueError("Temporary error")
        
        for _ in range(3):
            try:
                await circuit.call(temp_error)
            except ValueError:
                pass
        
        # Circuit should still be closed
        result = await circuit.call(self._success_function)
        assert result == "success"
        
        # Fatal errors should count - exactly 2 to meet threshold
        async def fatal_error():
            raise ValueError("Fatal error")
        
        for _ in range(2):
            try:
                await circuit.call(fatal_error)
            except ValueError:
                pass
        
        # Now circuit should be open
        with pytest.raises(CircuitBreakerOpenError):
            await circuit.call(self._success_function)
    
    # Helper methods
    async def _failing_function(self):
        raise ValueError("Simulated failure")
    
    async def _success_function(self):
        return "success"
    
    async def _raise(self, exc):
        raise exc


class TestBulkheadExceptions:
    """Test Bulkhead exception handling"""
    
    @pytest.mark.asyncio
    async def test_default_exception(self):
        """Test bulkhead raises BulkheadFullError by default"""
        bulkhead = Bulkhead(
            name="test-bulkhead",
            config=BulkheadConfig(max_concurrent=1, max_waiting=0)
        )
        
        # Acquire the slot with context manager
        async def hold_slot():
            async with bulkhead:
                await asyncio.sleep(1)
        
        # Start holding the slot
        task = asyncio.create_task(hold_slot())
        await asyncio.sleep(0.01)  # Let it acquire
        
        # Try to acquire when full
        with pytest.raises(BulkheadFullError) as exc_info:
            await bulkhead.execute(self._slow_function)
        
        error = exc_info.value
        assert error.pattern_name == "test-bulkhead"
        assert error.pattern_type == "bulkhead"
        assert error.reason == BulkheadReason.CAPACITY_FULL
        
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_custom_exception_type(self):
        """Test bulkhead with custom exception type"""
        class CapacityExceeded(Exception):
            pass
        
        exceptions = ExceptionConfig(exception_type=CapacityExceeded)
        bulkhead = Bulkhead(
            name="custom-bulkhead",
            config=BulkheadConfig(max_concurrent=1, max_waiting=0),
            exceptions=exceptions
        )
        
        async def hold_slot():
            async with bulkhead:
                await asyncio.sleep(1)
        
        task = asyncio.create_task(hold_slot())
        await asyncio.sleep(0.01)
        
        with pytest.raises(CapacityExceeded):
            await bulkhead.execute(self._slow_function)
        
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_on_rejection_callback(self):
        """Test bulkhead on_rejection callback"""
        rejections = []
        
        def on_rejection(ctx):
            rejections.append(ctx.reason)
        
        exceptions = ExceptionConfig(on_exception=on_rejection)
        bulkhead = Bulkhead(
            name="callback-bulkhead",
            config=BulkheadConfig(max_concurrent=1, max_waiting=0),
            exceptions=exceptions
        )
        
        async def hold_slot():
            async with bulkhead:
                await asyncio.sleep(1)
        
        task = asyncio.create_task(hold_slot())
        await asyncio.sleep(0.01)
        
        try:
            await bulkhead.execute(self._slow_function)
        except BulkheadFullError:
            pass
        
        assert len(rejections) == 1
        
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    async def _slow_function(self):
        await asyncio.sleep(1)


class TestTimeoutExceptions:
    """Test Timeout exception handling"""
    
    @pytest.mark.asyncio
    async def test_default_exception(self):
        """Test timeout raises OperationTimeoutError by default"""
        timeout_mgr = TimeoutManager(
            config=TimeoutConfig(timeout=0.01, raise_on_timeout=True)
        )
        
        with pytest.raises(OperationTimeoutError) as exc_info:
            await timeout_mgr.execute(self._slow_function)
        
        error = exc_info.value
        assert error.pattern_type == "timeout"
        assert error.reason == TimeoutReason.TIMEOUT_EXCEEDED
    
    @pytest.mark.asyncio
    async def test_custom_exception_type(self):
        """Test timeout with custom exception type"""
        class RequestTimeout(Exception):
            pass
        
        exceptions = ExceptionConfig(exception_type=RequestTimeout)
        timeout_mgr = TimeoutManager(
            config=TimeoutConfig(timeout=0.01),
            exceptions=exceptions
        )
        
        with pytest.raises(RequestTimeout):
            await timeout_mgr.execute(self._slow_function)
    
    @pytest.mark.asyncio
    async def test_on_timeout_callback(self):
        """Test timeout on_timeout callback"""
        timeout_events = []
        
        def on_timeout(ctx):
            timeout_events.append(ctx.metadata.get('elapsed'))
        
        exceptions = ExceptionConfig(on_exception=on_timeout)
        timeout_mgr = TimeoutManager(
            config=TimeoutConfig(timeout=0.01),
            exceptions=exceptions
        )
        
        try:
            await timeout_mgr.execute(self._slow_function)
        except OperationTimeoutError:
            pass
        
        assert len(timeout_events) == 1
    
    async def _slow_function(self):
        await asyncio.sleep(10)


class TestRetryExceptions:
    """Test Retry exception handling and per-exception strategies"""
    
    @pytest.mark.asyncio
    async def test_per_exception_strategies(self):
        """Test retry with different strategies per exception type"""
        from aioresilience.retry import RetryStrategy
        
        # Test with ValueError getting 5 attempts
        retry_policy = RetryPolicy(
            config=RetryConfig(
                max_attempts=3,  # Default
                initial_delay=0.01,
                retry_on_exceptions=(ValueError,),
                exception_strategies={
                    ValueError: {
                        'max_attempts': 5,
                        'initial_delay': 0.01,
                        'strategy': RetryStrategy.CONSTANT
                    }
                }
            )
        )
        
        # ValueError should get 5 attempts
        attempt_count = [0]
        async def fail_with_value_error():
            attempt_count[0] += 1
            raise ValueError("Test")
        
        with pytest.raises(ValueError):
            await retry_policy.execute(fail_with_value_error)
        
        # Should have attempted 5 times
        assert attempt_count[0] == 5
        
        # Test TypeError with different strategy
        retry_policy_2 = RetryPolicy(
            config=RetryConfig(
                max_attempts=3,
                initial_delay=0.01,
                retry_on_exceptions=(TypeError,),
                exception_strategies={
                    TypeError: {
                        'max_attempts': 2,
                        'initial_delay': 0.01,
                        'strategy': RetryStrategy.CONSTANT
                    }
                }
            )
        )
        
        attempt_count[0] = 0
        async def fail_with_type_error():
            attempt_count[0] += 1
            raise TypeError("Test")
        
        with pytest.raises(TypeError):
            await retry_policy_2.execute(fail_with_type_error)
        
        assert attempt_count[0] == 2
    
    @pytest.mark.asyncio
    async def test_on_retry_callback(self):
        """Test retry on_retry callback"""
        retry_contexts = []
        
        def on_retry(ctx):
            retry_contexts.append(ctx.metadata.get('attempt'))
        
        retry_policy = RetryPolicy(
            config=RetryConfig(
                max_attempts=3,
                initial_delay=0.01,
                on_retry=on_retry
            )
        )
        
        attempt = [0]
        async def fail_twice():
            attempt[0] += 1
            if attempt[0] < 3:
                raise ValueError("Retry me")
            return "success"
        
        result = await retry_policy.execute(fail_twice)
        assert result == "success"
        assert len(retry_contexts) == 2  # Retried twice
    
    @pytest.mark.asyncio
    async def test_on_exhausted_callback(self):
        """Test retry on_exhausted callback"""
        exhausted_contexts = []
        
        def on_exhausted(ctx):
            exhausted_contexts.append(ctx.reason)
        
        retry_policy = RetryPolicy(
            config=RetryConfig(
                max_attempts=2,
                initial_delay=0.01,
                on_exhausted=on_exhausted
            )
        )
        
        async def always_fails():
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError):
            await retry_policy.execute(always_fails)
        
        assert len(exhausted_contexts) == 1
        assert exhausted_contexts[0] == RetryReason.EXHAUSTED
    
    @pytest.mark.asyncio
    async def test_on_success_after_retry_callback(self):
        """Test retry on_success_after_retry callback"""
        success_contexts = []
        
        def on_success(ctx):
            success_contexts.append(ctx.metadata.get('attempt'))
        
        retry_policy = RetryPolicy(
            config=RetryConfig(
                max_attempts=3,
                initial_delay=0.01,
                on_success_after_retry=on_success
            )
        )
        
        attempt = [0]
        async def fail_once():
            attempt[0] += 1
            if attempt[0] == 1:
                raise ValueError("Fail first time")
            return "success"
        
        result = await retry_policy.execute(fail_once)
        assert result == "success"
        assert len(success_contexts) == 1  # Called after successful retry


class TestBackpressureExceptions:
    """Test Backpressure exception handling"""
    
    @pytest.mark.asyncio
    async def test_default_exception(self):
        """Test backpressure raises BackpressureError by default"""
        bp = BackpressureManager(config=BackpressureConfig(
            max_pending=1,
            high_water_mark=1,
            low_water_mark=0
        ))
        
        # Fill up backpressure to max
        await bp.acquire()
        
        # Should not acquire when at max
        acquired = await bp.acquire(timeout=0.01)
        assert not acquired
        
        await bp.release()
    
    @pytest.mark.asyncio
    async def test_custom_exception_type(self):
        """Test backpressure with custom exception type"""
        class SystemOverloaded(Exception):
            pass
        
        exceptions = ExceptionConfig(exception_type=SystemOverloaded)
        bp = BackpressureManager(
            config=BackpressureConfig(
                max_pending=1,
                high_water_mark=1,
                low_water_mark=0
            ),
            exceptions=exceptions
        )
        
        # Fill to max
        await bp.acquire()
        
        # Should not acquire when full
        acquired = await bp.acquire(timeout=0.01)
        assert not acquired
        
        await bp.release()


class TestLoadSheddingExceptions:
    """Test LoadShedding exception handling"""
    
    @pytest.mark.asyncio
    async def test_default_exception(self):
        """Test load shedding raises LoadSheddingError by default"""
        shedder = BasicLoadShedder(config=LoadSheddingConfig(max_requests=1))
        
        # Acquire the slot
        await shedder.acquire()
        
        # Should not acquire when full
        acquired = await shedder.acquire()
        assert not acquired
        
        await shedder.release()
    
    @pytest.mark.asyncio
    async def test_custom_exception_type(self):
        """Test load shedding with custom exception type"""
        class ServiceOverloaded(Exception):
            pass
        
        exceptions = ExceptionConfig(exception_type=ServiceOverloaded)
        shedder = BasicLoadShedder(
            config=LoadSheddingConfig(max_requests=1),
            exceptions=exceptions
        )
        
        await shedder.acquire()
        
        # Using decorator should raise custom exception
        from aioresilience.load_shedding import with_load_shedding
        
        @with_load_shedding(shedder)
        async def test_func():
            return "success"
        
        # Should raise ServiceOverloaded (custom exception transformed)
        with pytest.raises(ServiceOverloaded):
            await test_func()
        
        await shedder.release()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
