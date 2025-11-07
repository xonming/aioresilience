"""Debug test to understand circuit breaker failure counting"""

import asyncio
from aioresilience import CircuitBreaker
from aioresilience.exceptions import CircuitBreakerOpenError

async def test_circuit_debug():
    """Debug circuit breaker failure counting"""
    circuit = CircuitBreaker(
        name="debug-circuit",
        failure_threshold=2,
        failure_exceptions=(ValueError, TypeError)
    )
    
    print(f"Initial state: {circuit.state}")
    print(f"Initial failures: {circuit.metrics.consecutive_failures}")
    
    # Trigger first failure
    try:
        await circuit.call(lambda: (_ for _ in ()).throw(ValueError("test1")))
    except ValueError:
        print(f"After ValueError: state={circuit.state}, failures={circuit.metrics.consecutive_failures}")
    
    # Trigger second failure
    try:
        await circuit.call(lambda: (_ for _ in ()).throw(TypeError("test2")))
    except TypeError:
        print(f"After TypeError: state={circuit.state}, failures={circuit.metrics.consecutive_failures}")
    
    # Check if circuit is open
    print(f"\nFinal state: {circuit.state}")
    print(f"Final failures: {circuit.metrics.consecutive_failures}")
    
    # Check can_execute
    can_exec = await circuit.can_execute()
    print(f"can_execute() returned: {can_exec}")
    
    # Try to call - should raise CircuitBreakerOpenError
    try:
        result = await circuit.call(lambda: "success")
        print(f"ERROR: Circuit did not raise CircuitBreakerOpenError! Result: {result}")
    except CircuitBreakerOpenError as e:
        print(f"SUCCESS: Circuit is open and raised CircuitBreakerOpenError: {e}")
    except Exception as e:
        print(f"ERROR: Unexpected exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_circuit_debug())
