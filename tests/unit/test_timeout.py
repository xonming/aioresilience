"""
Tests for Timeout/Deadline Pattern
"""

import asyncio
import pytest
import time
from aioresilience import (
    TimeoutManager,
    TimeoutConfig,
    DeadlineManager,
    timeout,
    with_timeout,
    with_deadline,
    OperationTimeoutError,
)


class TestTimeoutManager:
    """Tests for TimeoutManager class"""
    
    @pytest.mark.asyncio
    async def test_successful_execution_within_timeout(self):
        """Test successful execution within timeout"""
        manager = TimeoutManager(config=TimeoutConfig(timeout=1.0))
        
        async def fast_func():
            await asyncio.sleep(0.1)
            return "success"
        
        result = await manager.execute(fast_func)
        
        assert result == "success"
        metrics = manager.get_metrics()
        assert metrics["successful_executions"] == 1
        assert metrics["timed_out_executions"] == 0
    
    @pytest.mark.asyncio
    async def test_timeout_exceeded_raises(self):
        """Test that timeout raises OperationTimeoutError"""
        manager = TimeoutManager(config=TimeoutConfig(timeout=0.1, raise_on_timeout=True))
        
        async def slow_func():
            await asyncio.sleep(1.0)
            return "too slow"
        
        with pytest.raises(OperationTimeoutError, match="exceeded timeout of 0.1s"):
            await manager.execute(slow_func)
        
        metrics = manager.get_metrics()
        assert metrics["timed_out_executions"] == 1
        assert metrics["successful_executions"] == 0
    
    @pytest.mark.asyncio
    async def test_timeout_exceeded_returns_none(self):
        """Test that timeout can return None instead of raising"""
        manager = TimeoutManager(config=TimeoutConfig(timeout=0.1, raise_on_timeout=False))
        
        async def slow_func():
            await asyncio.sleep(1.0)
            return "too slow"
        
        result = await manager.execute(slow_func)
        
        assert result is None
        metrics = manager.get_metrics()
        assert metrics["timed_out_executions"] == 1
    
    @pytest.mark.asyncio
    async def test_sync_function_timeout(self):
        """Test timeout with sync functions"""
        manager = TimeoutManager(config=TimeoutConfig(timeout=0.1))
        
        def slow_sync():
            time.sleep(1.0)
            return "too slow"
        
        with pytest.raises(OperationTimeoutError):
            await manager.execute(slow_sync)
    
    @pytest.mark.asyncio
    async def test_metrics_tracking(self):
        """Test that metrics are tracked correctly"""
        manager = TimeoutManager(config=TimeoutConfig(timeout=1.0))
        
        async def func():
            await asyncio.sleep(0.05)
            return "ok"
        
        # Execute multiple times
        for _ in range(3):
            await manager.execute(func)
        
        metrics = manager.get_metrics()
        assert metrics["total_executions"] == 3
        assert metrics["successful_executions"] == 3
        assert metrics["average_execution_time"] > 0.05
        assert metrics["average_execution_time"] < 0.1
    
    @pytest.mark.asyncio
    async def test_reset_metrics(self):
        """Test metrics reset"""
        manager = TimeoutManager(config=TimeoutConfig(timeout=1.0))
        
        async def func():
            return "ok"
        
        await manager.execute(func)
        
        metrics = manager.get_metrics()
        assert metrics["total_executions"] == 1
        
        manager.reset_metrics()
        
        metrics = manager.get_metrics()
        assert metrics["total_executions"] == 0
        assert metrics["successful_executions"] == 0
    
    def test_invalid_timeout(self):
        """Test validation of timeout value"""
        with pytest.raises(ValueError, match="timeout must be positive"):
            TimeoutConfig(timeout=0)
        
        with pytest.raises(ValueError, match="timeout must be positive"):
            TimeoutConfig(timeout=-1.0)


class TestTimeoutDecorator:
    """Tests for @timeout decorator"""
    
    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator usage"""
        @timeout(1.0)
        async def fast_func():
            await asyncio.sleep(0.1)
            return "success"
        
        result = await fast_func()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_decorator_timeout(self):
        """Test decorator with timeout"""
        @timeout(0.1)
        async def slow_func():
            await asyncio.sleep(1.0)
            return "too slow"
        
        with pytest.raises(OperationTimeoutError):
            await slow_func()
    
    @pytest.mark.asyncio
    async def test_decorator_with_args(self):
        """Test decorator with function arguments"""
        @timeout(1.0)
        async def add(a, b):
            await asyncio.sleep(0.01)
            return a + b
        
        result = await add(2, 3)
        assert result == 5
    
    @pytest.mark.asyncio
    async def test_decorator_no_raise(self):
        """Test decorator that returns None on timeout"""
        @timeout(0.1, raise_on_timeout=False)
        async def slow_func():
            await asyncio.sleep(1.0)
            return "too slow"
        
        result = await slow_func()
        assert result is None
    
    @pytest.mark.asyncio
    async def test_decorator_metrics_access(self):
        """Test accessing metrics through decorated function"""
        @timeout(1.0)
        async def func():
            return "ok"
        
        await func()
        
        metrics = func.timeout_manager.get_metrics()
        assert metrics["total_executions"] == 1
        assert metrics["successful_executions"] == 1


class TestWithTimeout:
    """Tests for with_timeout convenience function"""
    
    @pytest.mark.asyncio
    async def test_with_timeout_coroutine(self):
        """Test with_timeout with coroutine"""
        async def func():
            await asyncio.sleep(0.01)
            return "ok"
        
        result = await with_timeout(func, 1.0)
        assert result == "ok"
    
    @pytest.mark.asyncio
    async def test_with_timeout_exceeds(self):
        """Test with_timeout when timeout is exceeded"""
        async def slow_func():
            await asyncio.sleep(1.0)
            return "too slow"
        
        with pytest.raises(OperationTimeoutError):
            await with_timeout(slow_func, 0.1)
    
    @pytest.mark.asyncio
    async def test_with_timeout_args(self):
        """Test with_timeout with arguments"""
        async def add(a, b):
            return a + b
        
        result = await with_timeout(add, 1.0, 2, 3)
        assert result == 5


class TestDeadlineManager:
    """Tests for DeadlineManager class"""
    
    @pytest.mark.asyncio
    async def test_execution_within_deadline(self):
        """Test execution within deadline"""
        deadline = time.time() + 1.0
        manager = DeadlineManager(deadline=deadline)
        
        async def func():
            await asyncio.sleep(0.1)
            return "success"
        
        result = await manager.execute(func)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_deadline_exceeded(self):
        """Test deadline exceeded"""
        deadline = time.time() + 0.1
        manager = DeadlineManager(deadline=deadline, raise_on_deadline=True)
        
        async def slow_func():
            await asyncio.sleep(1.0)
            return "too slow"
        
        with pytest.raises(OperationTimeoutError, match="exceeded deadline"):
            await manager.execute(slow_func)
    
    @pytest.mark.asyncio
    async def test_deadline_already_passed(self):
        """Test when deadline has already passed"""
        deadline = time.time() - 1.0  # Past deadline
        manager = DeadlineManager(deadline=deadline, raise_on_deadline=True)
        
        async def func():
            return "ok"
        
        with pytest.raises(OperationTimeoutError, match="already expired"):
            await manager.execute(func)
    
    @pytest.mark.asyncio
    async def test_deadline_no_raise(self):
        """Test deadline that returns None instead of raising"""
        deadline = time.time() + 0.1
        manager = DeadlineManager(deadline=deadline, raise_on_deadline=False)
        
        async def slow_func():
            await asyncio.sleep(1.0)
            return "too slow"
        
        result = await manager.execute(slow_func)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_time_remaining(self):
        """Test time_remaining calculation"""
        deadline = time.time() + 5.0
        manager = DeadlineManager(deadline=deadline)
        
        remaining = manager.time_remaining()
        assert 4.9 < remaining <= 5.0
    
    @pytest.mark.asyncio
    async def test_is_expired(self):
        """Test is_expired check"""
        future_deadline = time.time() + 10.0
        manager = DeadlineManager(deadline=future_deadline)
        assert not manager.is_expired()
        
        past_deadline = time.time() - 1.0
        manager = DeadlineManager(deadline=past_deadline)
        assert manager.is_expired()


class TestWithDeadline:
    """Tests for with_deadline convenience function"""
    
    @pytest.mark.asyncio
    async def test_with_deadline_basic(self):
        """Test basic with_deadline usage"""
        deadline = time.time() + 1.0
        
        async def func():
            await asyncio.sleep(0.1)
            return "ok"
        
        result = await with_deadline(func, deadline)
        assert result == "ok"
    
    @pytest.mark.asyncio
    async def test_with_deadline_exceeds(self):
        """Test with_deadline when exceeded"""
        deadline = time.time() + 0.1
        
        async def slow_func():
            await asyncio.sleep(1.0)
            return "too slow"
        
        with pytest.raises(OperationTimeoutError):
            await with_deadline(slow_func, deadline)
    
    @pytest.mark.asyncio
    async def test_with_deadline_args(self):
        """Test with_deadline with arguments"""
        deadline = time.time() + 1.0
        
        async def multiply(a, b):
            return a * b
        
        result = await with_deadline(multiply, deadline, 3, 4)
        assert result == 12


class TestTimeoutConcurrency:
    """Tests for timeout behavior under concurrent execution"""
    
    @pytest.mark.asyncio
    async def test_concurrent_timeouts(self):
        """Test multiple concurrent operations with timeouts"""
        manager = TimeoutManager(config=TimeoutConfig(timeout=0.5))
        
        async def task(n):
            await asyncio.sleep(n * 0.1)
            return n
        
        # Start multiple tasks
        tasks = [manager.execute(task, i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        assert results == [0, 1, 2, 3, 4]
        metrics = manager.get_metrics()
        assert metrics["successful_executions"] == 5
    
    @pytest.mark.asyncio
    async def test_concurrent_mixed_results(self):
        """Test concurrent operations with mixed success/timeout"""
        manager = TimeoutManager(config=TimeoutConfig(timeout=0.15, raise_on_timeout=False))
        
        async def task(n):
            await asyncio.sleep(n * 0.1)
            return n
        
        # Some will succeed, some will timeout
        tasks = [manager.execute(task, i) for i in range(5)]
        results = await asyncio.gather(*tasks)
        
        # Tasks 0, 1 should succeed; 2, 3, 4 should timeout (return None)
        assert results[0] == 0
        assert results[1] == 1
        assert results[2] is None
        assert results[3] is None
        assert results[4] is None
