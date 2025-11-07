"""
Tests for Exception System

Tests the new exception handling system including:
- Base exception classes
- Reason enums
- Specific exception types
- ExceptionHandler
- Integration with patterns
"""

import pytest
import asyncio
from aioresilience.exceptions import (
    # Base
    ResilienceError,
    ExceptionContext,
    ExceptionAction,
    # Reasons
    CircuitBreakerReason,
    BulkheadReason,
    TimeoutReason,
    RetryReason,
    BackpressureReason,
    LoadSheddingReason,
    # Exceptions
    CircuitBreakerOpenError,
    BulkheadFullError,
    OperationTimeoutError,
    BackpressureError,
    LoadSheddingError,
    # Handler
    ExceptionHandler,
)


class TestResilienceError:
    """Test ResilienceError base exception"""
    
    def test_basic_creation(self):
        """Test creating basic ResilienceError"""
        error = ResilienceError("Test error")
        assert str(error) == "Test error"
        assert error.pattern_name is None
        assert error.pattern_type is None
        assert error.reason is None
        assert error.metadata == {}
    
    def test_with_pattern_info(self):
        """Test ResilienceError with pattern information"""
        error = ResilienceError(
            "Circuit open",
            pattern_name="api-circuit",
            pattern_type="circuit_breaker",
            reason=CircuitBreakerReason.CIRCUIT_OPEN,
            failure_count=5
        )
        assert str(error) == "Circuit open"
        assert error.pattern_name == "api-circuit"
        assert error.pattern_type == "circuit_breaker"
        assert error.reason == CircuitBreakerReason.CIRCUIT_OPEN
        assert error.metadata["failure_count"] == 5
    
    def test_repr(self):
        """Test ResilienceError repr"""
        error = ResilienceError(
            "Test",
            pattern_name="test-pattern",
            reason=CircuitBreakerReason.CIRCUIT_OPEN
        )
        repr_str = repr(error)
        assert "ResilienceError" in repr_str
        assert "test-pattern" in repr_str
        assert "CIRCUIT_OPEN" in repr_str


class TestExceptionContext:
    """Test ExceptionContext dataclass"""
    
    def test_basic_context(self):
        """Test creating basic context"""
        ctx = ExceptionContext(
            pattern_name="test-circuit",
            pattern_type="circuit_breaker",
            reason=CircuitBreakerReason.CIRCUIT_OPEN
        )
        assert ctx.pattern_name == "test-circuit"
        assert ctx.pattern_type == "circuit_breaker"
        assert ctx.reason == CircuitBreakerReason.CIRCUIT_OPEN
        assert ctx.original_exception is None
        assert ctx.metadata == {}
    
    def test_context_with_exception(self):
        """Test context with original exception"""
        original = ValueError("Original error")
        ctx = ExceptionContext(
            pattern_name="test",
            pattern_type="retry",
            reason=RetryReason.EXHAUSTED,
            original_exception=original,
            metadata={"attempts": 3}
        )
        assert ctx.original_exception == original
        assert ctx.metadata["attempts"] == 3
    
    def test_to_dict(self):
        """Test converting context to dictionary"""
        ctx = ExceptionContext(
            pattern_name="test",
            pattern_type="bulkhead",
            reason=BulkheadReason.CAPACITY_FULL,
            metadata={"current": 10, "max": 10}
        )
        d = ctx.to_dict()
        assert d["pattern_name"] == "test"
        assert d["pattern_type"] == "bulkhead"
        assert d["reason"] == "CAPACITY_FULL"
        assert d["metadata"] == {"current": 10, "max": 10}


class TestReasonEnums:
    """Test all reason enums are IntEnum"""
    
    def test_circuit_breaker_reason(self):
        """Test CircuitBreakerReason enum"""
        assert CircuitBreakerReason.CIRCUIT_OPEN == 0
        assert CircuitBreakerReason.TIMEOUT == 1
        assert CircuitBreakerReason.HALF_OPEN_REJECTION == 2
        assert isinstance(CircuitBreakerReason.CIRCUIT_OPEN, int)
    
    def test_bulkhead_reason(self):
        """Test BulkheadReason enum"""
        assert BulkheadReason.CAPACITY_FULL == 0
        assert BulkheadReason.QUEUE_FULL == 1
        assert BulkheadReason.TIMEOUT == 2
        assert isinstance(BulkheadReason.CAPACITY_FULL, int)
    
    def test_timeout_reason(self):
        """Test TimeoutReason enum"""
        assert TimeoutReason.TIMEOUT_EXCEEDED == 0
        assert TimeoutReason.DEADLINE_EXCEEDED == 1
        assert isinstance(TimeoutReason.TIMEOUT_EXCEEDED, int)
    
    def test_retry_reason(self):
        """Test RetryReason enum"""
        assert RetryReason.EXHAUSTED == 0
        assert RetryReason.NON_RETRYABLE == 1
        assert isinstance(RetryReason.EXHAUSTED, int)
    
    def test_backpressure_reason(self):
        """Test BackpressureReason enum"""
        assert BackpressureReason.SYSTEM_OVERLOADED == 0
        assert BackpressureReason.TIMEOUT_ACQUIRING == 1
        assert isinstance(BackpressureReason.SYSTEM_OVERLOADED, int)
    
    def test_load_shedding_reason(self):
        """Test LoadSheddingReason enum"""
        assert LoadSheddingReason.MAX_LOAD_EXCEEDED == 0
        assert LoadSheddingReason.PRIORITY_REJECTED == 1
        assert isinstance(LoadSheddingReason.MAX_LOAD_EXCEEDED, int)


class TestSpecificExceptions:
    """Test specific exception types"""
    
    def test_circuit_breaker_open_error(self):
        """Test CircuitBreakerOpenError"""
        error = CircuitBreakerOpenError(
            "Circuit is open",
            pattern_name="api",
            pattern_type="circuit_breaker",
            reason=CircuitBreakerReason.CIRCUIT_OPEN,
            state="OPEN"
        )
        assert isinstance(error, ResilienceError)
        assert str(error) == "Circuit is open"
        assert error.reason == CircuitBreakerReason.CIRCUIT_OPEN
        assert error.metadata["state"] == "OPEN"
    
    def test_bulkhead_full_error(self):
        """Test BulkheadFullError"""
        error = BulkheadFullError(
            "Bulkhead at capacity",
            pattern_name="db-pool",
            pattern_type="bulkhead",
            reason=BulkheadReason.CAPACITY_FULL,
            current_load=10
        )
        assert isinstance(error, ResilienceError)
        assert error.reason == BulkheadReason.CAPACITY_FULL
    
    def test_operation_timeout_error(self):
        """Test OperationTimeoutError"""
        error = OperationTimeoutError(
            "Operation timed out",
            pattern_name="slow-api",
            pattern_type="timeout",
            reason=TimeoutReason.TIMEOUT_EXCEEDED,
            timeout=5.0
        )
        assert isinstance(error, ResilienceError)
        assert error.reason == TimeoutReason.TIMEOUT_EXCEEDED
    
    def test_backpressure_error(self):
        """Test BackpressureError"""
        error = BackpressureError(
            "System overloaded",
            pattern_name="queue",
            pattern_type="backpressure",
            reason=BackpressureReason.SYSTEM_OVERLOADED
        )
        assert isinstance(error, ResilienceError)
    
    def test_load_shedding_error(self):
        """Test LoadSheddingError"""
        error = LoadSheddingError(
            "Load shed",
            pattern_name="api",
            pattern_type="load_shedding",
            reason=LoadSheddingReason.MAX_LOAD_EXCEEDED
        )
        assert isinstance(error, ResilienceError)


class TestExceptionHandler:
    """Test ExceptionHandler class"""
    
    @pytest.mark.asyncio
    async def test_basic_handler(self):
        """Test basic exception handler"""
        handler = ExceptionHandler(
            pattern_name="test",
            pattern_type="circuit_breaker",
            handled_exceptions=(ValueError,),
        )
        
        # Should handle ValueError
        assert handler.should_handle_exception(ValueError("test"))
        
        # Should not handle TypeError
        assert not handler.should_handle_exception(TypeError("test"))
    
    @pytest.mark.asyncio
    async def test_exception_predicate(self):
        """Test exception predicate filtering"""
        def is_retryable(exc):
            return "retryable" in str(exc).lower()
        
        handler = ExceptionHandler(
            pattern_name="test",
            pattern_type="retry",
            handled_exceptions=(Exception,),
            exception_predicate=is_retryable,
        )
        
        # Should handle retryable exceptions
        assert handler.should_handle_exception(ValueError("Retryable error"))
        
        # Should not handle non-retryable
        assert not handler.should_handle_exception(ValueError("Fatal error"))
    
    @pytest.mark.asyncio
    async def test_custom_exception_type(self):
        """Test raising custom exception type"""
        class CustomError(Exception):
            pass
        
        handler = ExceptionHandler(
            pattern_name="test",
            pattern_type="circuit_breaker",
            handled_exceptions=(Exception,),
            exception_type=CustomError,
        )
        
        action, exc = await handler.handle_exception(
            reason=CircuitBreakerReason.CIRCUIT_OPEN,
            original_exc=None,
            message="Custom error"
        )
        
        assert action == ExceptionAction.RAISE_TRANSFORMED
        assert isinstance(exc, CustomError)
    
    @pytest.mark.asyncio
    async def test_exception_transformer(self):
        """Test exception transformer"""
        def transform(exc, ctx):
            return ValueError(f"Transformed: {ctx.pattern_name}")
        
        handler = ExceptionHandler(
            pattern_name="test-pattern",
            pattern_type="circuit_breaker",
            handled_exceptions=(Exception,),
            exception_transformer=transform,
        )
        
        action, exc = await handler.handle_exception(
            reason=CircuitBreakerReason.CIRCUIT_OPEN,
            original_exc=None,
            message="Test"
        )
        
        assert action == ExceptionAction.RAISE_TRANSFORMED
        assert isinstance(exc, ValueError)
        assert "test-pattern" in str(exc)
    
    @pytest.mark.asyncio
    async def test_on_exception_callback(self):
        """Test on_exception callback"""
        callback_called = []
        
        def on_exception(ctx):
            callback_called.append(ctx.pattern_name)
        
        handler = ExceptionHandler(
            pattern_name="callback-test",
            pattern_type="bulkhead",
            handled_exceptions=(Exception,),
            on_exception=on_exception,
        )
        
        await handler.handle_exception(
            reason=BulkheadReason.CAPACITY_FULL,
            original_exc=None,
            message="Test"
        )
        
        assert len(callback_called) == 1
        assert callback_called[0] == "callback-test"
    
    @pytest.mark.asyncio
    async def test_async_callback(self):
        """Test async on_exception callback"""
        callback_called = []
        
        async def on_exception(ctx):
            await asyncio.sleep(0.01)
            callback_called.append(ctx.pattern_type)
        
        handler = ExceptionHandler(
            pattern_name="test",
            pattern_type="async-test",
            handled_exceptions=(Exception,),
            on_exception=on_exception,
        )
        
        await handler.handle_exception(
            reason=CircuitBreakerReason.CIRCUIT_OPEN,
            original_exc=None,
            message="Test"
        )
        
        assert len(callback_called) == 1
        assert callback_called[0] == "async-test"


class TestExceptionAction:
    """Test ExceptionAction enum"""
    
    def test_action_values(self):
        """Test ExceptionAction enum values"""
        assert ExceptionAction.RAISE_ORIGINAL == 0
        assert ExceptionAction.RAISE_TRANSFORMED == 1
        assert ExceptionAction.SUPPRESS == 2
        assert ExceptionAction.FALLBACK == 3
        
        # Verify it's an IntEnum
        assert isinstance(ExceptionAction.RAISE_ORIGINAL, int)
    
    def test_comparison_performance(self):
        """Test that IntEnum allows fast comparison"""
        action = ExceptionAction.RAISE_ORIGINAL
        
        # Should be able to compare with int
        assert action == 0
        assert action < 1
        assert action != 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
