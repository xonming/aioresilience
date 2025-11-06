"""
Centralized logging configuration for aioresilience.

By default, all logging is disabled (NullHandler) following Python library best practices.
Users can configure logging via:
1. Standard Python logging (configure_logging)
2. Custom handler callback (set_error_handler)
3. Complete disable (already default)

Examples:
    # Enable standard logging
    from aioresilience import configure_logging
    import logging
    configure_logging(logging.DEBUG)
    
    # Use loguru
    from aioresilience import set_error_handler
    from loguru import logger
    
    def loguru_handler(name, exc, ctx):
        logger.opt(exception=exc).error(f"[{name}] Error", **ctx)
    
    set_error_handler(loguru_handler)
    
    # Use structlog
    import structlog
    
    def structlog_handler(name, exc, ctx):
        structlog.get_logger().error("error", module=name, exception=str(exc), **ctx)
    
    set_error_handler(structlog_handler)
"""

import logging
from typing import Optional, Callable, Any

# Root logger for the library - silent by default
_root_logger = logging.getLogger('aioresilience')
_root_logger.addHandler(logging.NullHandler())
_root_logger.propagate = False  # Don't propagate to root

# Custom error handler (optional)
_error_handler: Optional[Callable[[str, Exception, dict], None]] = None


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance for a module.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def set_error_handler(handler: Optional[Callable[[str, Exception, dict], None]]) -> None:
    """
    Set custom error handler for all modules.
    
    This allows integration with any logging framework (loguru, structlog, etc.)
    
    Args:
        handler: Callable(logger_name, exception, context_dict) or None to disable
        
    Examples:
        # Use loguru
        from loguru import logger
        
        def loguru_handler(name, exc, ctx):
            logger.opt(exception=exc).error(f"[{name}] {exc}", **ctx)
        
        set_error_handler(loguru_handler)
        
        # Disable error logging
        set_error_handler(None)
    """
    global _error_handler
    _error_handler = handler


def configure_logging(
    level: int = logging.INFO, 
    handler: Optional[logging.Handler] = None,
    format_string: Optional[str] = None
) -> None:
    """
    Configure standard Python logging for aioresilience.
    
    Removes NullHandler and sets up proper logging output.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        handler: Custom handler or None for StreamHandler
        format_string: Custom format string or None for default
        
    Examples:
        # Basic configuration
        import logging
        from aioresilience import configure_logging
        configure_logging(logging.DEBUG)
        
        # Custom handler
        file_handler = logging.FileHandler('aioresilience.log')
        configure_logging(logging.INFO, handler=file_handler)
        
        # Custom format
        configure_logging(
            logging.DEBUG,
            format_string='%(asctime)s [%(name)s] %(levelname)s: %(message)s'
        )
    """
    # Clear existing handlers
    _root_logger.handlers.clear()
    
    # Create handler if not provided
    if handler is None:
        handler = logging.StreamHandler()
    
    # Set formatter
    if format_string is None:
        format_string = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)
    
    # Configure logger
    _root_logger.addHandler(handler)
    _root_logger.setLevel(level)
    _root_logger.propagate = False


def disable_logging() -> None:
    """
    Disable all aioresilience logging.
    
    Resets to default state (NullHandler only).
    """
    global _error_handler
    _error_handler = None
    _root_logger.handlers.clear()
    _root_logger.addHandler(logging.NullHandler())
    _root_logger.propagate = False


def log_error(logger_name: str, exception: Exception, **context: Any) -> None:
    """
    Internal error logging with custom handler support.
    
    Falls back to standard logging if no custom handler is set.
    Used internally by aioresilience modules for error reporting.
    
    Args:
        logger_name: Name of the logger/module
        exception: Exception that occurred
        **context: Additional context information
        
    Examples:
        # Internal use
        log_error(
            'aioresilience.events.emitter',
            ValueError("Handler failed"),
            handler_name='on_event',
            event_type='state_change'
        )
    """
    if _error_handler:
        try:
            _error_handler(logger_name, exception, context)
        except Exception as handler_error:
            # If custom handler fails, fall back to standard logging
            _root_logger.debug(
                f"[{logger_name}] Error handler failed. Original error: {exception.__class__.__name__}: {exception}",
                exc_info=False
            )
    else:
        # Fallback to standard logging (silent by default due to NullHandler)
        # Use root logger directly to ensure it works with configured handlers
        _root_logger.debug(
            f"[{logger_name}] {exception.__class__.__name__}: {exception}",
            extra=context,
            exc_info=False
        )


def is_logging_enabled() -> bool:
    """
    Check if logging is enabled (has handlers other than NullHandler).
    
    Returns:
        True if logging is configured, False if using default NullHandler
    """
    return (
        _error_handler is not None or
        any(not isinstance(h, logging.NullHandler) for h in _root_logger.handlers)
    )
