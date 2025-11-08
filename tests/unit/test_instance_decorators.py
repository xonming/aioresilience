"""
Tests for instance-based decorators

Verifies that all patterns have consistent instance-based decorators
that use existing instances instead of creating new ones.
"""

import pytest
from aioresilience import (
    CircuitBreaker, CircuitConfig,
    RetryPolicy, RetryConfig,
    TimeoutManager, TimeoutConfig,
    Bulkhead, BulkheadConfig,
    FallbackHandler, FallbackConfig,
    with_circuit_breaker,
    with_retry,
    with_timeout_manager,
    with_bulkhead,
    with_fallback_handler,
)


@pytest.mark.asyncio
async def test_with_circuit_breaker():
    """Test @with_circuit_breaker decorator uses existing instance"""
    circuit = CircuitBreaker(name="test", config=CircuitConfig(failure_threshold=2))
    
    call_count = 0
    
    @with_circuit_breaker(circuit)
    async def test_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Test error")
        return "success"
    
    # First two calls should fail and increment circuit failure count
    with pytest.raises(ValueError):
        await test_func()
    with pytest.raises(ValueError):
        await test_func()
    
    # Circuit should now be open
    from aioresilience import CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        await test_func()
    
    # Verify the same instance is being used
    metrics = circuit.get_metrics()
    assert metrics['failed_requests'] == 2
    assert test_func.circuit_breaker is circuit


@pytest.mark.asyncio
async def test_with_retry():
    """Test @with_retry decorator uses existing instance"""
    policy = RetryPolicy(config=RetryConfig(max_attempts=3, initial_delay=0.01))
    
    call_count = 0
    
    @with_retry(policy)
    async def test_func():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError("Test error")
        return "success"
    
    result = await test_func()
    assert result == "success"
    assert call_count == 3
    
    # Verify the same instance is being used
    metrics = policy.get_metrics()
    assert metrics['total_attempts'] == 3
    assert metrics['failed_attempts'] == 2  # 2 failures before success
    assert test_func.retry_policy is policy


@pytest.mark.asyncio
async def test_with_timeout_manager():
    """Test @with_timeout_manager decorator uses existing instance"""
    manager = TimeoutManager(config=TimeoutConfig(timeout=0.1))
    
    @with_timeout_manager(manager)
    async def test_func():
        import asyncio
        await asyncio.sleep(0.05)
        return "success"
    
    result = await test_func()
    assert result == "success"
    
    # Verify the same instance is being used
    metrics = manager.get_metrics()
    assert metrics['total_executions'] == 1
    assert metrics['successful_executions'] == 1
    assert test_func.timeout_manager is manager


@pytest.mark.asyncio
async def test_with_bulkhead():
    """Test @with_bulkhead decorator uses existing instance"""
    bulkhead = Bulkhead(name="test", config=BulkheadConfig(max_concurrent=2))
    
    @with_bulkhead(bulkhead)
    async def test_func():
        import asyncio
        await asyncio.sleep(0.01)
        return "success"
    
    result = await test_func()
    assert result == "success"
    
    # Verify the same instance is being used
    metrics = bulkhead.get_metrics()
    assert metrics['successful_requests'] == 1
    assert test_func.bulkhead is bulkhead


@pytest.mark.asyncio
async def test_with_fallback_handler():
    """Test @with_fallback_handler decorator uses existing instance"""
    handler = FallbackHandler(config=FallbackConfig(fallback="fallback_value"))
    
    @with_fallback_handler(handler)
    async def test_func():
        raise ValueError("Test error")
    
    result = await test_func()
    assert result == "fallback_value"
    
    # Verify the same instance is being used
    metrics = handler.get_metrics()
    assert metrics['fallback_executions'] == 1
    assert test_func.fallback_handler is handler


@pytest.mark.asyncio
async def test_decorator_instance_sharing():
    """Test that decorators share the same instance across multiple decorated functions"""
    circuit = CircuitBreaker(name="shared", config=CircuitConfig(failure_threshold=2))
    
    @with_circuit_breaker(circuit)
    async def func1():
        raise ValueError("Error in func1")
    
    @with_circuit_breaker(circuit)
    async def func2():
        raise ValueError("Error in func2")
    
    # Both functions should use the same circuit instance
    assert func1.circuit_breaker is circuit
    assert func2.circuit_breaker is circuit
    assert func1.circuit_breaker is func2.circuit_breaker
    
    # Failures in func1 should affect func2
    with pytest.raises(ValueError):
        await func1()
    with pytest.raises(ValueError):
        await func1()
    
    # Circuit should now be open for both functions
    from aioresilience import CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        await func2()
