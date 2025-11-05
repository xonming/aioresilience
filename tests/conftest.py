"""
Pytest configuration and fixtures for aioresilience tests
"""
import pytest
import asyncio
import gc


@pytest.fixture
def event_loop():
    """Create an event loop for each test"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    
    # Clean up pending tasks
    try:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    except Exception:
        pass
    
    # Close the loop
    loop.close()
    
    # Force garbage collection to clean up resources
    gc.collect()


@pytest.fixture
async def clean_circuit_breakers():
    """Clean up global circuit breaker manager after tests"""
    from aioresilience.circuit_breaker import _circuit_manager
    
    yield
    
    # Reset all circuit breakers
    await _circuit_manager.reset_all()
    # Clear the manager
    _circuit_manager.breakers.clear()


# You can add more fixtures here as needed
