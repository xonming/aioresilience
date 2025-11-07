"""
Exception Handler Configuration

Provides a clean way to configure exception handling across resilience patterns.
"""

from typing import Optional, Callable, Type, Tuple
from dataclasses import dataclass, field

from .base import ExceptionContext


@dataclass
class ExceptionConfig:
    """
    Configuration for exception handling in resilience patterns.
    
    This class provides a clean, reusable way to configure how patterns
    handle exceptions without cluttering constructors.
    
    Args:
        exception_type: Custom exception type to raise (pattern-specific default if None)
        exception_transformer: Function to transform exceptions before raising
        on_exception: Callback when exception is raised (e.g., on_failure, on_timeout)
        handled_exceptions: Tuple of exception types to handle (pattern-specific)
        exception_predicate: Optional predicate to filter exceptions
        
    Example:
        >>> # Simple custom exception
        >>> config = ExceptionConfig(exception_type=MyCustomError)
        
        >>> # With transformer
        >>> config = ExceptionConfig(
        ...     exception_transformer=lambda exc, ctx: CustomError(f"Failed: {ctx.pattern_name}")
        ... )
        
        >>> # With callback
        >>> config = ExceptionConfig(
        ...     on_exception=lambda ctx: logger.error(f"Failed: {ctx.reason}")
        ... )
    """
    
    exception_type: Optional[Type[Exception]] = None
    exception_transformer: Optional[Callable[[Exception, ExceptionContext], Exception]] = None
    on_exception: Optional[Callable[[ExceptionContext], None]] = None
    handled_exceptions: Optional[Tuple[Type[Exception], ...]] = None
    exception_predicate: Optional[Callable[[Exception], bool]] = None
    
    def __post_init__(self):
        """Validate configuration"""
        if self.exception_type is not None and not issubclass(self.exception_type, BaseException):
            raise ValueError("exception_type must be an exception class")


# Convenience function for backwards compatibility
def create_exception_config(
    exception_type: Optional[Type[Exception]] = None,
    exception_transformer: Optional[Callable[[Exception, ExceptionContext], Exception]] = None,
    on_exception: Optional[Callable[[ExceptionContext], None]] = None,
    handled_exceptions: Optional[Tuple[Type[Exception], ...]] = None,
    exception_predicate: Optional[Callable[[Exception], bool]] = None,
) -> ExceptionConfig:
    """
    Create an ExceptionConfig instance.
    
    This is a convenience function that provides the same interface as the dataclass constructor.
    """
    return ExceptionConfig(
        exception_type=exception_type,
        exception_transformer=exception_transformer,
        on_exception=on_exception,
        handled_exceptions=handled_exceptions,
        exception_predicate=exception_predicate,
    )
