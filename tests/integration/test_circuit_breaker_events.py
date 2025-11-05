"""
Integration tests for CircuitBreaker event emission
"""

import pytest
import asyncio
from aioresilience import CircuitBreaker
from aioresilience.events import global_bus, EventType


async def failing_operation():
    """Simulated failing operation"""
    raise ValueError("Test failure")


async def successful_operation():
    """Simulated successful operation"""
    return "success"


class TestCircuitBreakerEvents:
    """Test circuit breaker event emission"""
    
    def setup_method(self):
        """Clear global bus before each test"""
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_emits_failure_events(self):
        """Test circuit breaker emits failure events"""
        circuit = CircuitBreaker(name="test", failure_threshold=3)
        
        failure_events = []
        
        @circuit.events.on("call_failure")
        async def capture_failures(event):
            failure_events.append(event)
        
        # Cause failures
        for _ in range(3):
            try:
                await circuit.call(failing_operation)
            except:
                pass
        
        assert len(failure_events) == 3
        assert failure_events[0].failure_count == 1
        assert failure_events[1].failure_count == 2
        assert failure_events[2].failure_count == 3
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_emits_success_events(self):
        """Test circuit breaker emits success events"""
        circuit = CircuitBreaker(name="test")
        
        success_events = []
        
        @circuit.events.on("call_success")
        async def capture_success(event):
            success_events.append(event)
        
        # Successful calls
        for _ in range(3):
            await circuit.call(successful_operation)
        
        assert len(success_events) == 3
        assert all(e.event_type == EventType.CALL_SUCCESS for e in success_events)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_emits_state_change_to_open(self):
        """Test circuit breaker emits state change when opening"""
        circuit = CircuitBreaker(name="test", failure_threshold=2)
        
        state_changes = []
        
        @circuit.events.on("state_change")
        async def capture_state_change(event):
            state_changes.append(event)
        
        # Cause circuit to open
        for _ in range(3):
            try:
                await circuit.call(failing_operation)
            except:
                pass
        
        # Should have one state change: CLOSED -> OPEN
        assert len(state_changes) == 1
        assert state_changes[0].old_state == "closed"
        assert state_changes[0].new_state == "open"
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_reset_emits_event(self):
        """Test manual reset emits reset event"""
        circuit = CircuitBreaker(name="test", failure_threshold=2)
        
        reset_events = []
        
        @circuit.events.on("circuit_reset")
        async def capture_reset(event):
            reset_events.append(event)
        
        # Open the circuit
        for _ in range(3):
            try:
                await circuit.call(failing_operation)
            except:
                pass
        
        # Reset
        await circuit.reset()
        
        assert len(reset_events) == 1
        assert reset_events[0].event_type == EventType.CIRCUIT_RESET
        assert reset_events[0].new_state == "closed"
    
    @pytest.mark.asyncio
    async def test_global_bus_receives_circuit_events(self):
        """Test global bus receives events from circuit breakers"""
        all_events = []
        
        @global_bus.on("*")
        async def capture_all(event):
            all_events.append(event)
        
        circuit1 = CircuitBreaker(name="circuit-1", failure_threshold=2)
        circuit2 = CircuitBreaker(name="circuit-2", failure_threshold=2)
        
        # Generate events from both circuits
        await circuit1.call(successful_operation)
        await circuit2.call(successful_operation)
        
        try:
            await circuit1.call(failing_operation)
        except:
            pass
        
        try:
            await circuit2.call(failing_operation)
        except:
            pass
        
        # Should have events from both circuits
        circuit1_events = [e for e in all_events if e.pattern_name == "circuit-1"]
        circuit2_events = [e for e in all_events if e.pattern_name == "circuit-2"]
        
        assert len(circuit1_events) == 2  # 1 success, 1 failure
        assert len(circuit2_events) == 2  # 1 success, 1 failure
