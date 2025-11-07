"""
Exception handler base class for resilience patterns.

Provides unified exception handling with customization points.
"""

import asyncio
from typing import Optional, Callable, Type, Tuple
from .base import ExceptionAction, ExceptionContext, ResilienceError


class ExceptionHandler:
    """
    Base exception handler with customization points.
    
    Provides:
    - Exception type filtering
    - Custom exception transformers
    - Exception factory pattern
    - Callback hooks
    
    All resilience patterns can inherit from this or use it as a mixin.
    """
    
    def __init__(
        self,
        pattern_name: str,
        pattern_type: str,
        
        # Input: Which exceptions to handle
        handled_exceptions: Tuple[Type[Exception], ...] = (Exception,),
        exception_predicate: Optional[Callable[[Exception], bool]] = None,
        
        # Output: How to transform/raise exceptions
        exception_type: Optional[Type[Exception]] = None,
        exception_transformer: Optional[Callable[[Exception, ExceptionContext], Exception]] = None,
        
        # Hooks
        on_exception: Optional[Callable[[ExceptionContext], None]] = None,
    ):
        """
        Initialize exception handler.
        
        Args:
            pattern_name: Name of the pattern instance
            pattern_type: Type of pattern (circuit_breaker, bulkhead, etc.)
            handled_exceptions: Tuple of exception types to catch
            exception_predicate: Optional function to filter exceptions
            exception_type: Custom exception class to raise (simple mode)
            exception_transformer: Function to transform exceptions (advanced mode)
            on_exception: Callback when exception occurs
        """
        self.pattern_name = pattern_name
        self.pattern_type = pattern_type
        self.handled_exceptions = handled_exceptions
        self.exception_predicate = exception_predicate
        self._exception_type = exception_type
        self._exception_transformer = exception_transformer
        self.on_exception = on_exception
    
    def should_handle_exception(self, exc: Exception) -> bool:
        """
        Check if an exception should be handled by this pattern.
        
        Args:
            exc: Exception to check
            
        Returns:
            True if exception should be handled
        """
        # Check type
        if not isinstance(exc, self.handled_exceptions):
            return False
        
        # Check predicate if provided
        if self.exception_predicate:
            try:
                return self.exception_predicate(exc)
            except Exception:
                # If predicate fails, be safe and handle the exception
                return True
        
        return True
    
    async def handle_exception(
        self,
        reason: int,
        original_exc: Optional[Exception] = None,
        message: Optional[str] = None,
        **metadata
    ) -> Tuple[ExceptionAction, Exception]:
        """
        Process an exception and return the action to take.
        
        Args:
            reason: Reason code (IntEnum value)
            original_exc: Original exception if any
            message: Default error message
            **metadata: Additional context
            
        Returns:
            Tuple of (action, exception_to_raise)
        """
        # Build context
        context = ExceptionContext(
            pattern_name=self.pattern_name,
            pattern_type=self.pattern_type,
            reason=reason,
            original_exception=original_exc,
            metadata=metadata,
        )
        
        # Call user callback
        if self.on_exception:
            try:
                if asyncio.iscoroutinefunction(self.on_exception):
                    await self.on_exception(context)
                else:
                    self.on_exception(context)
            except Exception as callback_error:
                # Log callback errors but don't let them break exception handling
                import logging
                logging.getLogger(__name__).error(
                    f"Exception handler '{self.pattern_name}': Error in on_exception callback: "
                    f"{type(callback_error).__name__}: {callback_error}"
                )
        
        # Create exception to raise
        exc = self._create_exception(context, message or str(original_exc or ""))
        
        # Determine action
        if self._exception_transformer:
            return ExceptionAction.RAISE_TRANSFORMED, exc
        elif self._exception_type:
            return ExceptionAction.RAISE_TRANSFORMED, exc
        else:
            return ExceptionAction.RAISE_ORIGINAL, exc
    
    def _create_exception(self, context: ExceptionContext, default_message: str) -> Exception:
        """
        Create exception to raise based on configuration.
        
        Args:
            context: Exception context
            default_message: Default error message
            
        Returns:
            Exception instance to raise
        """
        # Use transformer if provided (highest priority)
        if self._exception_transformer:
            try:
                exc = self._exception_transformer(context.original_exception, context)
                return exc
            except Exception:
                # If transformer fails, fall through to defaults
                pass
        
        # Use custom exception type if provided
        if self._exception_type:
            exc = self._exception_type(default_message)
            
            # Add context if it's a ResilienceError
            if isinstance(exc, ResilienceError):
                exc.pattern_name = context.pattern_name
                exc.pattern_type = context.pattern_type
                exc.reason = context.reason
                exc.metadata = context.metadata
            
            return exc
        
        # Fallback to original or create generic
        if context.original_exception:
            return context.original_exception
        
        return Exception(default_message)
