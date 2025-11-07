"""
Unit tests for event system
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
)


class TestEventEmitter:
    """Test EventEmitter functionality"""
    
    @pytest.mark.asyncio
    async def test_emitter_initialization(self):
        """Test event emitter initialization"""
        emitter = EventEmitter("test-pattern")
        assert emitter.pattern_name == "test-pattern"
        assert emitter.handler_count == 0
    
    @pytest.mark.asyncio
    async def test_on_decorator(self):
        """Test registering handler with decorator"""
        emitter = EventEmitter("test")
        handler_called = False
        received_event = None
        
        @emitter.on(EventType.STATE_CHANGE.value)
        async def handler(event):
            nonlocal handler_called, received_event
            handler_called = True
            received_event = event
        
        assert emitter.handler_count == 1
        
        # Emit event
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        await emitter.emit(event)
        
        assert handler_called
        assert received_event == event
    
    @pytest.mark.asyncio
    async def test_add_handler_programmatic(self):
        """Test adding handler programmatically"""
        emitter = EventEmitter("test")
        handler_called = False
        
        async def handler(event):
            nonlocal handler_called
            handler_called = True
        
        emitter.add_handler(EventType.STATE_CHANGE.value, handler)
        assert emitter.handler_count == 1
        
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        await emitter.emit(event)
        
        assert handler_called
    
    @pytest.mark.asyncio
    async def test_wildcard_handler(self):
        """Test wildcard handler receives all events"""
        emitter = EventEmitter("test")
        events_received = []
        
        @emitter.on("*")
        async def wildcard_handler(event):
            events_received.append(event.event_type)
        
        # Emit different events
        for event_type in [EventType.STATE_CHANGE, EventType.CALL_SUCCESS, EventType.CALL_FAILURE]:
            event = ResilienceEvent(
                pattern_type=PatternType.CIRCUIT_BREAKER,
                event_type=event_type,
                pattern_name="test"
            )
            await emitter.emit(event)
        
        assert len(events_received) == 3
        assert EventType.STATE_CHANGE in events_received
        assert EventType.CALL_SUCCESS in events_received
        assert EventType.CALL_FAILURE in events_received
    
    @pytest.mark.asyncio
    async def test_remove_handler(self):
        """Test removing handlers"""
        emitter = EventEmitter("test")
        handler_called = False
        
        async def handler(event):
            nonlocal handler_called
            handler_called = True
        
        emitter.add_handler(EventType.STATE_CHANGE.value, handler)
        assert emitter.handler_count == 1
        
        emitter.remove_handler(EventType.STATE_CHANGE.value, handler)
        assert emitter.handler_count == 0
        
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        await emitter.emit(event)
        
        assert not handler_called
    
    @pytest.mark.asyncio
    async def test_multiple_handlers_for_same_event(self):
        """Test multiple handlers for same event type"""
        emitter = EventEmitter("test")
        call_count = 0
        
        @emitter.on(EventType.STATE_CHANGE.value)
        async def handler1(event):
            nonlocal call_count
            call_count += 1
        
        @emitter.on(EventType.STATE_CHANGE.value)
        async def handler2(event):
            nonlocal call_count
            call_count += 1
        
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        await emitter.emit(event)
        
        assert call_count == 2
    
    @pytest.mark.asyncio
    async def test_handler_exception_doesnt_stop_others(self):
        """Test that handler exception doesn't stop other handlers"""
        emitter = EventEmitter("test")
        handler2_called = False
        
        @emitter.on(EventType.STATE_CHANGE.value)
        async def failing_handler(event):
            raise ValueError("Handler error")
        
        @emitter.on(EventType.STATE_CHANGE.value)
        async def working_handler(event):
            nonlocal handler2_called
            handler2_called = True
        
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        await emitter.emit(event)
        
        assert handler2_called


class TestGlobalEventBus:
    """Test GlobalEventBus functionality"""
    
    def setup_method(self):
        """Clear global bus before each test"""
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_global_bus_initially_inactive(self):
        """Test global bus is inactive when no handlers"""
        assert not global_bus.is_active
        assert global_bus.handler_count == 0
    
    @pytest.mark.asyncio
    async def test_global_bus_auto_enables(self):
        """Test global bus auto-enables when handler added"""
        assert not global_bus.is_active
        
        @global_bus.on("state_change")
        async def handler(event):
            pass
        
        assert global_bus.is_active
        assert global_bus.handler_count == 1
        assert EventEmitter.is_global_bus_enabled()
    
    @pytest.mark.asyncio
    async def test_global_bus_receives_events(self):
        """Test global bus receives events from emitters"""
        handler_called = False
        received_event = None
        
        @global_bus.on(EventType.STATE_CHANGE.value)
        async def handler(event):
            nonlocal handler_called, received_event
            handler_called = True
            received_event = event
        
        # Create emitter and emit event
        emitter = EventEmitter("test")
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        await emitter.emit(event)
        
        assert handler_called
        assert received_event == event
    
    @pytest.mark.asyncio
    async def test_global_wildcard_handler(self):
        """Test global wildcard handler receives all events"""
        events_received = []
        
        @global_bus.on("*")
        async def wildcard_handler(event):
            events_received.append(event.event_type)
        
        emitter = EventEmitter("test")
        
        for event_type in [EventType.STATE_CHANGE, EventType.CALL_SUCCESS]:
            event = ResilienceEvent(
                pattern_type=PatternType.CIRCUIT_BREAKER,
                event_type=event_type,
                pattern_name="test"
            )
            await emitter.emit(event)
        
        assert len(events_received) == 2
    
    @pytest.mark.asyncio
    async def test_clear_deactivates_bus(self):
        """Test clearing handlers deactivates global bus"""
        @global_bus.on("state_change")
        async def handler(event):
            pass
        
        assert global_bus.is_active
        
        global_bus.clear()
        
        assert not global_bus.is_active
        assert global_bus.handler_count == 0
        assert not EventEmitter.is_global_bus_enabled()
    
    @pytest.mark.asyncio
    async def test_local_and_global_handlers_both_called(self):
        """Test both local and global handlers are called"""
        local_called = False
        global_called = False
        
        emitter = EventEmitter("test")
        
        @emitter.on(EventType.STATE_CHANGE.value)
        async def local_handler(event):
            nonlocal local_called
            local_called = True
        
        @global_bus.on(EventType.STATE_CHANGE.value)
        async def global_handler(event):
            nonlocal global_called
            global_called = True
        
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        await emitter.emit(event)
        
        assert local_called
        assert global_called


class TestEventTypes:
    """Test event type enums and classes"""
    
    def test_pattern_type_enum(self):
        """Test PatternType enum values"""
        assert PatternType.CIRCUIT_BREAKER.value == 0
        assert PatternType.RATE_LIMITER.value == 4
        assert PatternType.BULKHEAD.value == 1
    
    def test_event_type_enum(self):
        """Test EventType enum values"""
        assert EventType.STATE_CHANGE.value == 1
        assert EventType.CALL_SUCCESS.value == 2
        assert EventType.CALL_FAILURE.value == 3
    
    def test_resilience_event_to_dict(self):
        """Test ResilienceEvent to_dict method"""
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test",
            metadata={"key": "value"}
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["pattern_type"] == "circuit_breaker"
        assert event_dict["event_type"] == "state_change"
        assert event_dict["pattern_name"] == "test"
        assert "timestamp" in event_dict
        assert event_dict["metadata"]["key"] == "value"
    
    def test_circuit_breaker_event_to_dict(self):
        """Test CircuitBreakerEvent to_dict includes extra fields"""
        event = CircuitBreakerEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test",
            old_state="closed",
            new_state="open",
            failure_count=5
        )
        
        event_dict = event.to_dict()
        
        assert event_dict["old_state"] == "closed"
        assert event_dict["new_state"] == "open"
        assert event_dict["failure_count"] == 5
