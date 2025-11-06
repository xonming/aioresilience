"""
Unit tests for centralized logging configuration
"""

import pytest
import logging
from aioresilience.logging import (
    configure_logging,
    set_error_handler,
    disable_logging,
    is_logging_enabled,
    log_error,
)


class TestLoggingConfiguration:
    """Test logging configuration"""
    
    def setup_method(self):
        """Reset logging state before each test"""
        disable_logging()
    
    def teardown_method(self):
        """Reset logging state after each test"""
        disable_logging()
    
    def test_default_state_is_disabled(self):
        """Test that logging is disabled by default"""
        assert not is_logging_enabled()
    
    def test_configure_logging_enables_logging(self):
        """Test that configure_logging enables logging"""
        configure_logging(logging.DEBUG)
        assert is_logging_enabled()
    
    def test_disable_logging_resets_state(self):
        """Test that disable_logging resets to default state"""
        configure_logging(logging.INFO)
        assert is_logging_enabled()
        
        disable_logging()
        assert not is_logging_enabled()
    
    def test_custom_error_handler(self):
        """Test setting custom error handler"""
        errors_captured = []
        
        def custom_handler(name, exc, ctx):
            errors_captured.append({
                'name': name,
                'exception': exc,
                'context': ctx
            })
        
        set_error_handler(custom_handler)
        assert is_logging_enabled()
        
        # Trigger error logging
        log_error('test.module', ValueError("test error"), key="value")
        
        assert len(errors_captured) == 1
        assert errors_captured[0]['name'] == 'test.module'
        assert isinstance(errors_captured[0]['exception'], ValueError)
        assert errors_captured[0]['context']['key'] == 'value'
    
    def test_custom_error_handler_none_disables(self):
        """Test that setting error handler to None disables custom handling"""
        errors_captured = []
        
        def custom_handler(name, exc, ctx):
            errors_captured.append(exc)
        
        set_error_handler(custom_handler)
        assert is_logging_enabled()
        
        set_error_handler(None)
        assert not is_logging_enabled()
        
        # This should not call custom handler
        log_error('test.module', ValueError("test error"))
        assert len(errors_captured) == 0
    
    def test_log_error_with_default_logging(self):
        """Test log_error falls back to standard logging when no custom handler"""
        # Configure standard logging
        import io
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        configure_logging(logging.DEBUG, handler=handler)
        
        log_error('test.module', RuntimeError("test error"), custom_field="value")
        
        # Should have logged something
        output = stream.getvalue()
        assert 'RuntimeError' in output or 'test error' in output
    
    def test_configure_logging_with_custom_format(self):
        """Test configure_logging with custom format string"""
        import io
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        
        configure_logging(
            logging.INFO,
            handler=handler,
            format_string='%(levelname)s: %(message)s'
        )
        
        # Get logger and log something
        logger = logging.getLogger('aioresilience')
        logger.info("Test message")
        
        output = stream.getvalue()
        assert 'INFO: Test message' in output
    
    def test_error_handler_exception_handling(self):
        """Test that failing error handler doesn't break the system"""
        def failing_handler(name, exc, ctx):
            raise RuntimeError("Handler failed")
        
        set_error_handler(failing_handler)
        
        # This should not raise, even though handler fails
        log_error('test.module', ValueError("test error"))
        # If we get here, test passes


class TestLoggingIntegration:
    """Test logging integration with event system"""
    
    def setup_method(self):
        """Reset state"""
        disable_logging()
        from aioresilience.events import global_bus
        global_bus.clear()
    
    def teardown_method(self):
        """Cleanup"""
        disable_logging()
        from aioresilience.events import global_bus
        global_bus.clear()
    
    @pytest.mark.asyncio
    async def test_event_handler_errors_logged_with_custom_handler(self):
        """Test that event handler errors are captured by custom error handler"""
        from aioresilience.events import EventEmitter, ResilienceEvent, PatternType, EventType
        
        errors_captured = []
        
        def custom_handler(name, exc, ctx):
            errors_captured.append({
                'name': name,
                'exception': exc,
                'context': ctx
            })
        
        set_error_handler(custom_handler)
        
        # Create emitter with failing handler
        emitter = EventEmitter("test-pattern")
        
        @emitter.on("state_change")
        async def failing_handler(event):
            raise ValueError("Handler intentionally failed")
        
        # Emit event
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test-pattern"
        )
        
        await emitter.emit(event)
        
        # Should have captured the error
        assert len(errors_captured) == 1
        assert isinstance(errors_captured[0]['exception'], ValueError)
        assert 'test-pattern' in errors_captured[0]['name']
    
    @pytest.mark.asyncio
    async def test_global_bus_errors_logged_with_custom_handler(self):
        """Test that global bus handler errors are captured"""
        from aioresilience.events import global_bus, EventEmitter, ResilienceEvent, PatternType, EventType
        
        errors_captured = []
        
        def custom_handler(name, exc, ctx):
            errors_captured.append(exc)
        
        set_error_handler(custom_handler)
        
        # Add failing global handler
        @global_bus.on("*")
        async def failing_global_handler(event):
            raise RuntimeError("Global handler failed")
        
        # Create emitter and emit event
        emitter = EventEmitter("test")
        event = ResilienceEvent(
            pattern_type=PatternType.CIRCUIT_BREAKER,
            event_type=EventType.STATE_CHANGE,
            pattern_name="test"
        )
        
        await emitter.emit(event)
        
        # Should have captured the error
        assert len(errors_captured) == 1
        assert isinstance(errors_captured[0], RuntimeError)
