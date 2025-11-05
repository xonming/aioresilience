"""
Example: Using the Event System for Monitoring

Shows how to use local event handlers and global event bus
"""

import asyncio
import logging
from aioresilience import CircuitBreaker
from aioresilience.events import global_bus, EventType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    # Example 1: Local event handlers (per pattern)
    print("=" * 60)
    print("Example 1: Local Event Handlers")
    print("=" * 60)
    
    circuit = CircuitBreaker(name="api", failure_threshold=3)
    
    # Register local handler using decorator
    @circuit.events.on("state_change")
    async def log_state_change(event):
        print(f"🔔 Circuit '{event.pattern_name}': "
              f"{event.old_state} → {event.new_state}")
    
    @circuit.events.on("call_failure")
    async def alert_on_failure(event):
        print(f"❌ Call failed! Consecutive failures: {event.failure_count}")
    
    # Simulate failures
    for i in range(5):
        try:
            await circuit.call(failing_operation)
        except Exception:
            pass
    
    print()
    
    # Example 2: Global event bus (monitor all patterns)
    print("=" * 60)
    print("Example 2: Global Event Bus")
    print("=" * 60)
    
    # Register global handlers
    @global_bus.on("state_change")
    async def monitor_all_state_changes(event):
        print(f"🌐 [GLOBAL] State change in {event.pattern_name}: "
              f"{event.old_state} → {event.new_state}")
    
    @global_bus.on("*")  # Listen to ALL events
    async def log_all_events(event):
        logger.info(f"Event: {event.event_type.value} from {event.pattern_name}")
    
    # Create multiple patterns
    circuit1 = CircuitBreaker(name="service-1", failure_threshold=2)
    circuit2 = CircuitBreaker(name="service-2", failure_threshold=2)
    
    # Both circuits will forward events to global bus
    print("\nTriggering events from multiple circuits...")
    
    for _ in range(3):
        try:
            await circuit1.call(failing_operation)
        except:
            pass
    
    for _ in range(3):
        try:
            await circuit2.call(failing_operation)
        except:
            pass
    
    print()
    
    # Example 3: Metrics collection via events
    print("=" * 60)
    print("Example 3: Metrics Collection")
    print("=" * 60)
    
    metrics = {
        "state_changes": 0,
        "failures": 0,
        "successes": 0,
    }
    
    @global_bus.on("state_change")
    async def count_state_changes(event):
        metrics["state_changes"] += 1
    
    @global_bus.on("call_failure")
    async def count_failures(event):
        metrics["failures"] += 1
    
    @global_bus.on("call_success")
    async def count_successes(event):
        metrics["successes"] += 1
    
    circuit3 = CircuitBreaker(name="monitored", failure_threshold=2)
    
    # Mix of failures and successes
    for i in range(10):
        try:
            if i % 3 == 0:
                await circuit3.call(failing_operation)
            else:
                await circuit3.call(successful_operation)
        except:
            pass
    
    print("\nCollected Metrics:")
    print(f"  State Changes: {metrics['state_changes']}")
    print(f"  Failures: {metrics['failures']}")
    print(f"  Successes: {metrics['successes']}")
    
    print()
    print("=" * 60)
    print(f"Global bus is active: {global_bus.is_active}")
    print(f"Global handlers registered: {global_bus.handler_count}")
    print("=" * 60)


async def failing_operation():
    """Simulated failing operation"""
    await asyncio.sleep(0.01)
    raise ValueError("Simulated failure")


async def successful_operation():
    """Simulated successful operation"""
    await asyncio.sleep(0.01)
    return "success"


if __name__ == "__main__":
    asyncio.run(main())
