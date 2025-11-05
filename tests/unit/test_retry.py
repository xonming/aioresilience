"""
Tests for Retry Pattern
"""

import asyncio
import pytest
import time
from aioresilience import (
    RetryPolicy,
    RetryStrategy,
    retry,
    RetryPolicies,
)


class TestRetryPolicy:
    """Tests for RetryPolicy class"""
    
    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(self):
        """Test successful execution without needing retries"""
        policy = RetryPolicy(max_attempts=3)
        
        call_count = 0
        
        async def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await policy.execute(successful_func)
        
        assert result == "success"
        assert call_count == 1
        metrics = policy.get_metrics()
        assert metrics["total_attempts"] == 1
        assert metrics["successful_attempts"] == 1
        assert metrics["failed_attempts"] == 0
    
    @pytest.mark.asyncio
    async def test_retry_on_exception(self):
        """Test retry on exceptions"""
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.01,
            retry_on_exceptions=(ValueError,)
        )
        
        call_count = 0
        
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("temporary error")
            return "success"
        
        result = await policy.execute(failing_func)
        
        assert result == "success"
        assert call_count == 3
        metrics = policy.get_metrics()
        assert metrics["total_attempts"] == 3
        assert metrics["successful_attempts"] == 1
        assert metrics["failed_attempts"] == 2
    
    @pytest.mark.asyncio
    async def test_retries_exhausted(self):
        """Test all retries exhausted"""
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.01,
        )
        
        call_count = 0
        
        async def always_failing():
            nonlocal call_count
            call_count += 1
            raise ValueError("permanent error")
        
        with pytest.raises(ValueError, match="permanent error"):
            await policy.execute(always_failing)
        
        assert call_count == 3
        metrics = policy.get_metrics()
        assert metrics["total_attempts"] == 3
        assert metrics["failed_attempts"] == 3
        assert metrics["retries_exhausted"] == 1
    
    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff strategy"""
        policy = RetryPolicy(
            max_attempts=4,
            initial_delay=0.1,
            backoff_multiplier=2.0,
            strategy=RetryStrategy.EXPONENTIAL,
            jitter=0.0,  # No jitter for predictable testing
        )
        
        call_count = 0
        
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise ValueError()
            return "success"
        
        start = time.time()
        result = await policy.execute(failing_func)
        duration = time.time() - start
        
        # Expected delays: 0.1, 0.2, 0.4 = 0.7 total
        assert result == "success"
        assert duration >= 0.7
        assert duration < 1.0  # Some tolerance
    
    @pytest.mark.asyncio
    async def test_linear_backoff(self):
        """Test linear backoff strategy"""
        policy = RetryPolicy(
            max_attempts=4,
            initial_delay=0.1,
            backoff_multiplier=0.1,
            strategy=RetryStrategy.LINEAR,
            jitter=0.0,
        )
        
        call_count = 0
        
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 4:
                raise ValueError()
            return "success"
        
        start = time.time()
        result = await policy.execute(failing_func)
        duration = time.time() - start
        
        # Expected delays: 0.1, 0.2, 0.3 = 0.6 total
        assert result == "success"
        assert duration >= 0.6
        assert duration < 0.9
    
    @pytest.mark.asyncio
    async def test_constant_backoff(self):
        """Test constant backoff strategy"""
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.1,
            strategy=RetryStrategy.CONSTANT,
            jitter=0.0,
        )
        
        call_count = 0
        
        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError()
            return "success"
        
        start = time.time()
        result = await policy.execute(failing_func)
        duration = time.time() - start
        
        # Expected delays: 0.1, 0.1 = 0.2 total
        assert result == "success"
        assert duration >= 0.2
        assert duration < 0.4
    
    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Test max delay capping"""
        policy = RetryPolicy(
            max_attempts=5,
            initial_delay=1.0,
            max_delay=2.0,
            backoff_multiplier=10.0,
            strategy=RetryStrategy.EXPONENTIAL,
            jitter=0.0,
        )
        
        # Delays should be capped at max_delay
        assert policy._calculate_delay(1) == 1.0
        assert policy._calculate_delay(2) == 2.0  # 10.0 capped to 2.0
        assert policy._calculate_delay(3) == 2.0  # 100.0 capped to 2.0
    
    @pytest.mark.asyncio
    async def test_retry_on_result(self):
        """Test retry based on result condition"""
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.01,
            retry_on_result=lambda x: x is None,
        )
        
        call_count = 0
        
        async def sometimes_none():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return None
            return "success"
        
        result = await policy.execute(sometimes_none)
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_non_retryable_exception(self):
        """Test that non-retryable exceptions are not retried"""
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.01,
            retry_on_exceptions=(ValueError,),
        )
        
        call_count = 0
        
        async def wrong_exception():
            nonlocal call_count
            call_count += 1
            raise TypeError("non-retryable")
        
        with pytest.raises(TypeError, match="non-retryable"):
            await policy.execute(wrong_exception)
        
        # Should not retry
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_sync_function_execution(self):
        """Test retry with sync functions"""
        policy = RetryPolicy(max_attempts=3, initial_delay=0.01)
        
        call_count = 0
        
        def sync_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError()
            return "success"
        
        result = await policy.execute(sync_func)
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_reset_metrics(self):
        """Test metrics reset"""
        policy = RetryPolicy(max_attempts=2)
        
        async def func():
            return "ok"
        
        await policy.execute(func)
        
        metrics = policy.get_metrics()
        assert metrics["total_attempts"] == 1
        
        policy.reset_metrics()
        
        metrics = policy.get_metrics()
        assert metrics["total_attempts"] == 0
        assert metrics["successful_attempts"] == 0


class TestRetryDecorator:
    """Tests for @retry decorator"""
    
    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator usage"""
        call_count = 0
        
        @retry(max_attempts=3, initial_delay=0.01)
        async def decorated_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError()
            return "success"
        
        result = await decorated_func()
        
        assert result == "success"
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_decorator_with_args(self):
        """Test decorator with function arguments"""
        @retry(max_attempts=3, initial_delay=0.01)
        async def add(a, b):
            return a + b
        
        result = await add(2, 3)
        assert result == 5
    
    @pytest.mark.asyncio
    async def test_decorator_metrics_access(self):
        """Test accessing metrics through decorated function"""
        @retry(max_attempts=3, initial_delay=0.01)
        async def func():
            return "ok"
        
        await func()
        
        metrics = func.retry_policy.get_metrics()
        assert metrics["total_attempts"] == 1
        assert metrics["successful_attempts"] == 1


class TestRetryPolicies:
    """Tests for predefined retry policies"""
    
    @pytest.mark.asyncio
    async def test_default_policy(self):
        """Test default retry policy"""
        policy = RetryPolicies.default()
        
        assert policy.max_attempts == 3
        assert policy.initial_delay == 1.0
    
    @pytest.mark.asyncio
    async def test_aggressive_policy(self):
        """Test aggressive retry policy"""
        policy = RetryPolicies.aggressive()
        
        assert policy.max_attempts == 5
        assert policy.initial_delay == 0.1
    
    @pytest.mark.asyncio
    async def test_conservative_policy(self):
        """Test conservative retry policy"""
        policy = RetryPolicies.conservative()
        
        assert policy.max_attempts == 3
        assert policy.strategy == RetryStrategy.LINEAR
    
    @pytest.mark.asyncio
    async def test_network_policy(self):
        """Test network-oriented retry policy"""
        policy = RetryPolicies.network()
        
        assert ConnectionError in policy.retry_on_exceptions
        assert TimeoutError in policy.retry_on_exceptions


class TestRetryEdgeCases:
    """Tests for edge cases and error handling"""
    
    def test_invalid_max_attempts(self):
        """Test validation of max_attempts"""
        with pytest.raises(ValueError, match="max_attempts must be at least 1"):
            RetryPolicy(max_attempts=0)
    
    def test_invalid_initial_delay(self):
        """Test validation of initial_delay"""
        with pytest.raises(ValueError, match="initial_delay must be non-negative"):
            RetryPolicy(initial_delay=-1.0)
    
    def test_invalid_max_delay(self):
        """Test validation of max_delay"""
        with pytest.raises(ValueError, match="max_delay must be >= initial_delay"):
            RetryPolicy(initial_delay=10.0, max_delay=5.0)
    
    def test_invalid_backoff_multiplier(self):
        """Test validation of backoff_multiplier"""
        with pytest.raises(ValueError, match="backoff_multiplier must be positive"):
            RetryPolicy(backoff_multiplier=0)
        
        with pytest.raises(ValueError, match="backoff_multiplier must be positive"):
            RetryPolicy(backoff_multiplier=-1.0)
        
        # For exponential, must be >= 1.0
        with pytest.raises(ValueError, match="backoff_multiplier must be >= 1.0 for exponential strategy"):
            RetryPolicy(backoff_multiplier=0.5, strategy=RetryStrategy.EXPONENTIAL)
    
    def test_invalid_jitter(self):
        """Test validation of jitter"""
        with pytest.raises(ValueError, match="jitter must be between 0.0 and 1.0"):
            RetryPolicy(jitter=1.5)
    
    @pytest.mark.asyncio
    async def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness to delays"""
        policy = RetryPolicy(
            max_attempts=3,
            initial_delay=1.0,
            jitter=0.5,
        )
        
        # Calculate delays multiple times to check variation
        delays = [policy._calculate_delay(1) for _ in range(10)]
        
        # All delays should be different (with high probability)
        assert len(set(delays)) > 1
        
        # All delays should be close to initial_delay
        for delay in delays:
            assert 0.5 <= delay <= 1.5
