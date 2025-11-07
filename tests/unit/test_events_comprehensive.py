"""
Comprehensive unit tests to improve event system coverage
"""

import pytest
import asyncio
from aioresilience.events import (
    EventEmitter,
    global_bus,
    PatternType,
    EventType,
    ResilienceEvent,
    CircuitBreakerEvent,
    RateLimitEvent,
    BulkheadEvent,
    LoadShedderEvent,
    RetryEvent,
    TimeoutEvent,
    FallbackEvent,
)


class TestEventTypesToDict:
    """Test to_dict methods for all event types"""
    
    def test_rate_limit_event_to_dict(self):
        """Test RateLimitEvent to_dict"""
        event = RateLimitEvent(
            pattern_type=PatternType.RATE_LIMITER,
            event_type=EventType.REQUEST_ALLOWED,
            pattern_name="test",
            user_id="user123",
            limit="100/minute",
            current_count=50,
            remaining=50,
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["user_id"] == "user123"
        assert event_dict["limit"] == "100/minute"
        assert event_dict["current_count"] == 50
        assert event_dict["remaining"] == 50
    
    def test_bulkhead_event_to_dict(self):
        """Test BulkheadEvent to_dict"""
        event = BulkheadEvent(
            pattern_type=PatternType.BULKHEAD,
            event_type=EventType.SLOT_ACQUIRED,
            pattern_name="test",
            active_count=10,
            waiting_count=5,
            max_concurrent=20,
            max_waiting=10,
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["active_count"] == 10
        assert event_dict["waiting_count"] == 5
        assert event_dict["max_concurrent"] == 20
        assert event_dict["max_waiting"] == 10
    
    def test_load_shedder_event_to_dict(self):
        """Test LoadShedderEvent to_dict"""
        event = LoadShedderEvent(
            pattern_type=PatternType.LOAD_SHEDDER,
            event_type=EventType.REQUEST_SHED,
            pattern_name="test",
            active_requests=100,
            max_requests=100,
            load_level="critical",
            reason="System overloaded",
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["active_requests"] == 100
        assert event_dict["max_requests"] == 100
        assert event_dict["load_level"] == "critical"
        assert event_dict["reason"] == "System overloaded"
    
    def test_retry_event_to_dict(self):
        """Test RetryEvent to_dict"""
        event = RetryEvent(
            pattern_type=PatternType.RETRY,
            event_type=EventType.RETRY_ATTEMPT,
            pattern_name="test",
            attempt=2,
            max_attempts=3,
            delay=1.5,
            error="Connection timeout",
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["attempt"] == 2
        assert event_dict["max_attempts"] == 3
        assert event_dict["delay"] == 1.5
        assert event_dict["error"] == "Connection timeout"
    
    def test_timeout_event_to_dict(self):
        """Test TimeoutEvent to_dict"""
        event = TimeoutEvent(
            pattern_type=PatternType.TIMEOUT,
            event_type=EventType.TIMEOUT_OCCURRED,
            pattern_name="test",
            timeout_value=5.0,
            elapsed=6.5,
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["timeout_value"] == 5.0
        assert event_dict["elapsed"] == 6.5
    
    def test_fallback_event_to_dict(self):
        """Test FallbackEvent to_dict"""
        event = FallbackEvent(
            pattern_type=PatternType.FALLBACK,
            event_type=EventType.FALLBACK_EXECUTED,
            pattern_name="test",
            primary_error="Database error",
            fallback_value="cached_value",
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["primary_error"] == "Database error"
        assert event_dict["fallback_value"] == "cached_value"


class TestGlobalBusRemoveHandler:
    """Test global bus handler removal"""
    
    def setup_method(self):
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_remove_handler_from_global_bus(self):
        """Test removing handler from global bus"""
        handler_called = False
        
        async def handler(event):
            nonlocal handler_called
            handler_called = True
        
        # Add and then remove
        global_bus.add_handler("test_event", handler)
        global_bus.remove_handler("test_event", handler)
        
        # Should not be called after removal
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        await global_bus.emit(event)
        
        assert not handler_called
    
    @pytest.mark.asyncio
    async def test_remove_wildcard_handler_from_global_bus(self):
        """Test removing wildcard handler from global bus"""
        handler_called = False
        
        async def handler(event):
            nonlocal handler_called
            handler_called = True
        
        # Add and then remove wildcard
        global_bus.add_handler("*", handler)
        global_bus.remove_handler("*", handler)
        
        # Should not be called
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        await global_bus.emit(event)
        
        assert not handler_called
    
    @pytest.mark.asyncio
    async def test_remove_nonexistent_handler_does_not_error(self):
        """Test removing non-existent handler doesn't raise error"""
        async def handler(event):
            pass
        
        # Should not raise error
        global_bus.remove_handler("nonexistent", handler)
        global_bus.remove_handler("*", handler)


class TestEventEmitterEdgeCases:
    """Test edge cases for EventEmitter"""
    
    @pytest.mark.asyncio
    async def test_emitter_with_name_parameter(self):
        """Test creating emitter with pattern_name"""
        emitter = EventEmitter(pattern_name="my-pattern")
        assert emitter.pattern_name == "my-pattern"
    
    @pytest.mark.asyncio
    async def test_multiple_wildcard_handlers(self):
        """Test multiple wildcard handlers all receive events"""
        emitter = EventEmitter("test")
        
        calls = []
        
        @emitter.on("*")
        async def handler1(event):
            calls.append("handler1")
        
        @emitter.on("*")
        async def handler2(event):
            calls.append("handler2")
        
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        await emitter.emit(event)
        
        assert "handler1" in calls
        assert "handler2" in calls
        assert len(calls) == 2
    
    @pytest.mark.asyncio
    async def test_handler_count_property(self):
        """Test handler_count property"""
        emitter = EventEmitter("test")
        
        assert emitter.handler_count == 0
        
        @emitter.on("event1")
        async def handler1(event):
            pass
        
        assert emitter.handler_count == 1
        
        @emitter.on("event2")
        async def handler2(event):
            pass
        
        assert emitter.handler_count == 2
        
        @emitter.on("*")
        async def wildcard(event):
            pass
        
        assert emitter.handler_count == 3


class TestGlobalBusProperties:
    """Test global bus properties and methods"""
    
    def setup_method(self):
        global_bus.clear()
    
    def test_is_active_property(self):
        """Test is_active property"""
        global_bus.clear()
        assert not global_bus.is_active
        
        @global_bus.on("test")
        async def handler(event):
            pass
        
        assert global_bus.is_active
    
    def test_handler_count_property(self):
        """Test handler_count property"""
        global_bus.clear()
        assert global_bus.handler_count == 0
        
        @global_bus.on("test1")
        async def handler1(event):
            pass
        
        @global_bus.on("test2")
        async def handler2(event):
            pass
        
        assert global_bus.handler_count == 2
    
    @pytest.mark.asyncio
    async def test_on_decorator_syntax(self):
        """Test @global_bus.on decorator syntax"""
        event_received = None
        
        @global_bus.on(EventType.STATE_CHANGE.value)
        async def my_handler(event):
            nonlocal event_received
            event_received = event
        
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        await global_bus.emit(event)
        
        assert event_received == event


class TestEventMetadata:
    """Test event metadata handling"""
    
    def test_event_with_metadata(self):
        """Test event with custom metadata"""
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test",
            metadata={"custom_field": "custom_value", "count": 42}
        )
        
        event_dict = event.to_dict()
        
        assert "metadata" in event_dict
        assert event_dict["metadata"]["custom_field"] == "custom_value"
        assert event_dict["metadata"]["count"] == 42
    
    def test_event_without_metadata(self):
        """Test event without metadata"""
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        
        event_dict = event.to_dict()
        
        # Metadata defaults to empty dict
        assert event_dict["metadata"] == {} or event_dict["metadata"] is None


class TestEventTimestamp:
    """Test event timestamp generation"""
    
    def test_event_has_timestamp(self):
        """Test that events have timestamps"""
        import time
        before = time.time()
        
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        
        after = time.time()
        
        assert before <= event.timestamp <= after
        
        event_dict = event.to_dict()
        assert "timestamp" in event_dict
        assert event_dict["timestamp"] == event.timestamp


class TestEventEmitterUtilityMethods:
    """Test EventEmitter utility methods"""
    
    def test_is_global_bus_enabled_classmethod(self):
        """Test is_global_bus_enabled class method"""
        global_bus.clear()
        
        # Initially disabled
        assert not EventEmitter.is_global_bus_enabled()
        
        # Enable by adding handler to global bus
        @global_bus.on("test")
        async def handler(event):
            pass
        
        # Now enabled
        assert EventEmitter.is_global_bus_enabled()
    
    def test_get_global_bus_classmethod(self):
        """Test get_global_bus class method"""
        bus = EventEmitter.get_global_bus()
        assert bus is global_bus
