"""
Tests for Fallback Pattern
"""

import asyncio
import pytest
from aioresilience import (
    FallbackHandler,
    FallbackConfig,
    ExceptionConfig,
    ChainedFallback,
    fallback,
    chained_fallback,
    with_fallback,
)


class TestFallbackHandler:
    """Tests for FallbackHandler class"""
    
    @pytest.mark.asyncio
    async def test_successful_execution_no_fallback(self):
        """Test successful execution without needing fallback"""
        handler = FallbackHandler(config=FallbackConfig(fallback="fallback_value"))
        
        async def successful_func():
            return "success"
        
        result = await handler.execute(successful_func)
        
        assert result == "success"
        metrics = handler.get_metrics()
        assert metrics["successful_executions"] == 1
        assert metrics["fallback_executions"] == 0
    
    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """Test fallback is used on exception"""
        handler = FallbackHandler(
            config=FallbackConfig(
                fallback="fallback_value",
                fallback_on_exceptions=(ValueError,)
            )
        )
        
        async def failing_func():
            raise ValueError("error")
        
        result = await handler.execute(failing_func)
        
        assert result == "fallback_value"
        metrics = handler.get_metrics()
        assert metrics["successful_executions"] == 0
        assert metrics["fallback_executions"] == 1
    
    @pytest.mark.asyncio
    async def test_fallback_callable(self):
        """Test fallback with callable"""
        def get_fallback():
            return "callable_fallback"
        
        handler = FallbackHandler(config=FallbackConfig(fallback=get_fallback))
        
        async def failing_func():
            raise Exception("error")
        
        result = await handler.execute(failing_func)
        
        assert result == "callable_fallback"
        metrics = handler.get_metrics()
        assert metrics["fallback_executions"] == 1
    
    @pytest.mark.asyncio
    async def test_fallback_async_callable(self):
        """Test fallback with async callable"""
        async def get_fallback_async():
            await asyncio.sleep(0.01)
            return "async_fallback"
        
        handler = FallbackHandler(config=FallbackConfig(fallback=get_fallback_async))
        
        async def failing_func():
            raise Exception("error")
        
        result = await handler.execute(failing_func)
        
        assert result == "async_fallback"
        metrics = handler.get_metrics()
        assert metrics["fallback_executions"] == 1
    
    @pytest.mark.asyncio
    async def test_fallback_with_args(self):
        """Test fallback receives function arguments"""
        def get_fallback(x, y):
            return f"fallback_{x}_{y}"
        
        handler = FallbackHandler(config=FallbackConfig(fallback=get_fallback))
        
        async def failing_func(x, y):
            raise Exception("error")
        
        result = await handler.execute(failing_func, 1, 2)
        
        assert result == "fallback_1_2"
    
    @pytest.mark.asyncio
    async def test_fallback_failure_reraise(self):
        """Test that fallback failure is reraised"""
        def failing_fallback():
            raise RuntimeError("fallback_error")
        
        handler = FallbackHandler(
            config=FallbackConfig(
                fallback=failing_fallback,
                reraise_on_fallback_failure=True
            )
        )
        
        async def failing_func():
            raise ValueError("primary_error")
        
        from aioresilience import FallbackFailedError
        
        with pytest.raises(FallbackFailedError):
            await handler.execute(failing_func)
        
        metrics = handler.get_metrics()
        assert metrics["failed_executions"] == 1
        assert metrics["fallback_executions"] == 0
    
    @pytest.mark.asyncio
    async def test_fallback_failure_no_reraise(self):
        """Test that fallback failure can be suppressed"""
        def failing_fallback():
            raise RuntimeError("fallback_error")
        
        handler = FallbackHandler(
            config=FallbackConfig(
                fallback=failing_fallback,
                reraise_on_fallback_failure=False
            )
        )
        
        async def failing_func():
            raise ValueError("primary_error")
        
        result = await handler.execute(failing_func)
        
        assert result is None
        metrics = handler.get_metrics()
        assert metrics["failed_executions"] == 1
    
    @pytest.mark.asyncio
    async def test_non_fallback_exception(self):
        """Test that non-fallback exceptions propagate"""
        handler = FallbackHandler(
            config=FallbackConfig(
                fallback="fallback_value",
                fallback_on_exceptions=(ValueError,)
            )
        )
        
        async def func():
            raise TypeError("non_fallback_exception")
        
        with pytest.raises(TypeError, match="non_fallback_exception"):
            await handler.execute(func)
        
        # Should not trigger fallback
        metrics = handler.get_metrics()
        assert metrics["fallback_executions"] == 0
    
    @pytest.mark.asyncio
    async def test_sync_function(self):
        """Test fallback with sync functions"""
        handler = FallbackHandler(config=FallbackConfig(fallback="fallback"))
        
        def failing_sync():
            raise Exception("error")
        
        result = await handler.execute(failing_sync)
        
        assert result == "fallback"
    
    @pytest.mark.asyncio
    async def test_reset_metrics(self):
        """Test metrics reset"""
        handler = FallbackHandler(config=FallbackConfig(fallback="fallback"))
        
        async def func():
            return "ok"
        
        await handler.execute(func)
        
        metrics = handler.get_metrics()
        assert metrics["total_executions"] == 1
        
        handler.reset_metrics()
        
        metrics = handler.get_metrics()
        assert metrics["total_executions"] == 0


class TestFallbackDecorator:
    """Tests for @fallback decorator"""
    
    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic decorator usage"""
        @fallback("fallback_value")
        async def func():
            raise Exception("error")
        
        result = await func()
        assert result == "fallback_value"
    
    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Test decorator with successful execution"""
        @fallback("fallback_value")
        async def func():
            return "success"
        
        result = await func()
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_decorator_with_args(self):
        """Test decorator with function arguments"""
        @fallback(lambda a, b: a * 10)
        async def divide(a, b):
            if b == 0:
                raise ZeroDivisionError()
            return a / b
        
        # Success case
        result = await divide(10, 2)
        assert result == 5.0
        
        # Fallback case
        result = await divide(5, 0)
        assert result == 50  # 5 * 10
    
    @pytest.mark.asyncio
    async def test_decorator_metrics_access(self):
        """Test accessing metrics through decorated function"""
        @fallback("fallback")
        async def func():
            return "ok"
        
        await func()
        
        metrics = func.fallback_handler.get_metrics()
        assert metrics["successful_executions"] == 1


class TestChainedFallback:
    """Tests for ChainedFallback class"""
    
    @pytest.mark.asyncio
    async def test_first_fallback_succeeds(self):
        """Test when first fallback succeeds"""
        handler = ChainedFallback("fallback1", "fallback2", "fallback3")
        
        async def failing_func():
            raise Exception("error")
        
        result = await handler.execute(failing_func)
        
        assert result == "fallback1"
        metrics = handler.get_metrics()
        assert metrics["fallback_executions"] == 1
    
    @pytest.mark.asyncio
    async def test_second_fallback_succeeds(self):
        """Test when first fallback fails but second succeeds"""
        def failing_fallback():
            raise Exception("fallback1_failed")
        
        handler = ChainedFallback(failing_fallback, "fallback2", "fallback3")
        
        async def failing_func():
            raise Exception("error")
        
        result = await handler.execute(failing_func)
        
        assert result == "fallback2"
        metrics = handler.get_metrics()
        assert metrics["fallback_executions"] == 1
    
    @pytest.mark.asyncio
    async def test_all_fallbacks_fail(self):
        """Test when all fallbacks fail"""
        def failing_fb1():
            raise Exception("fb1_failed")
        
        def failing_fb2():
            raise Exception("fb2_failed")
        
        handler = ChainedFallback(failing_fb1, failing_fb2)
        
        async def failing_func():
            raise Exception("error")
        
        with pytest.raises(Exception, match="fb2_failed"):
            await handler.execute(failing_func)
        
        metrics = handler.get_metrics()
        assert metrics["failed_executions"] == 1
    
    @pytest.mark.asyncio
    async def test_mixed_fallback_types(self):
        """Test with mixed static and callable fallbacks"""
        def failing_callable():
            raise Exception("callable_failed")
        
        async def async_fallback():
            return "async_success"
        
        handler = ChainedFallback(
            failing_callable,
            "static_fallback"  # This should be used
        )
        
        async def failing_func():
            raise Exception("error")
        
        result = await handler.execute(failing_func)
        assert result == "static_fallback"
    
    @pytest.mark.asyncio
    async def test_no_fallbacks_provided(self):
        """Test that at least one fallback is required"""
        with pytest.raises(ValueError, match="At least one fallback must be provided"):
            ChainedFallback()
    
    @pytest.mark.asyncio
    async def test_primary_success_no_fallback(self):
        """Test that fallbacks are not used when primary succeeds"""
        handler = ChainedFallback("fb1", "fb2", "fb3")
        
        async def successful_func():
            return "success"
        
        result = await handler.execute(successful_func)
        
        assert result == "success"
        metrics = handler.get_metrics()
        assert metrics["successful_executions"] == 1
        assert metrics["fallback_executions"] == 0


class TestChainedFallbackDecorator:
    """Tests for @chained_fallback decorator"""
    
    @pytest.mark.asyncio
    async def test_decorator_basic(self):
        """Test basic chained fallback decorator"""
        @chained_fallback("fb1", "fb2", "fb3")
        async def func():
            raise Exception("error")
        
        result = await func()
        assert result == "fb1"
    
    @pytest.mark.asyncio
    async def test_decorator_chain_progression(self):
        """Test fallback chain progression"""
        def fb1():
            raise Exception("fb1_failed")
        
        def fb2():
            raise Exception("fb2_failed")
        
        @chained_fallback(fb1, fb2, "fb3")
        async def func():
            raise Exception("primary_failed")
        
        result = await func()
        assert result == "fb3"
    
    @pytest.mark.asyncio
    async def test_decorator_metrics_access(self):
        """Test accessing metrics through decorated function"""
        @chained_fallback("fb1", "fb2")
        async def func():
            raise Exception("error")
        
        await func()
        
        metrics = func.fallback_handler.get_metrics()
        assert metrics["fallback_executions"] == 1


class TestWithFallback:
    """Tests for with_fallback convenience function"""
    
    @pytest.mark.asyncio
    async def test_with_fallback_basic(self):
        """Test basic with_fallback usage"""
        async def func():
            raise Exception("error")
        
        result = await with_fallback(func, "fallback_value")
        assert result == "fallback_value"
    
    @pytest.mark.asyncio
    async def test_with_fallback_success(self):
        """Test with_fallback when function succeeds"""
        async def func():
            return "success"
        
        result = await with_fallback(func, "fallback_value")
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_with_fallback_args(self):
        """Test with_fallback with arguments"""
        async def divide(a, b):
            if b == 0:
                raise ZeroDivisionError()
            return a / b
        
        result = await with_fallback(divide, -1, a=10, b=0)
        assert result == -1


class TestFallbackIntegration:
    """Integration tests for fallback patterns"""
    
    @pytest.mark.asyncio
    async def test_fallback_with_retry_simulation(self):
        """Test fallback pattern in retry-like scenario"""
        attempts = 0
        
        @fallback(lambda: {"status": "degraded"})
        async def fetch_data():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise Exception("temporary_error")
            return {"status": "ok"}
        
        # First call fails and uses fallback
        result1 = await fetch_data()
        assert result1 == {"status": "degraded"}
        
        # Reset for next test
        attempts = 0
        
        # Simulate retry succeeding
        result2 = await fetch_data()
        assert result2 == {"status": "degraded"}
        result3 = await fetch_data()
        assert result3 == {"status": "degraded"}
        result4 = await fetch_data()
        assert result4 == {"status": "ok"}
    
    @pytest.mark.asyncio
    async def test_tiered_fallbacks(self):
        """Test multi-tier fallback strategy"""
        # Simulates: try cache -> try backup API -> return default
        
        cache_available = False
        backup_api_available = True
        
        async def get_from_cache():
            if not cache_available:
                raise Exception("cache_miss")
            return {"source": "cache"}
        
        async def get_from_backup():
            if not backup_api_available:
                raise Exception("backup_unavailable")
            await asyncio.sleep(0.01)
            return {"source": "backup"}
        
        @chained_fallback(
            get_from_cache,
            get_from_backup,
            {"source": "default"}
        )
        async def get_data():
            raise Exception("primary_failed")
        
        # Cache miss, backup succeeds
        result = await get_data()
        assert result == {"source": "backup"}
        
        # All fail, use default
        backup_api_available = False
        result = await get_data()
        assert result == {"source": "default"}
    
    @pytest.mark.asyncio
    async def test_concurrent_fallbacks(self):
        """Test multiple concurrent operations with fallbacks"""
        @fallback("fallback")
        async def task(fail: bool):
            if fail:
                raise Exception("error")
            return "success"
        
        tasks = [
            task(True),   # Should use fallback
            task(False),  # Should succeed
            task(True),   # Should use fallback
            task(False),  # Should succeed
        ]
        
        results = await asyncio.gather(*tasks)
        
        assert results == ["fallback", "success", "fallback", "success"]
