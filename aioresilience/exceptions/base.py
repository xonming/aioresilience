"""
Base exception classes and types for aioresilience.
"""

from enum import IntEnum
from dataclasses import dataclass, field
from typing import Any, Optional


class ExceptionAction(IntEnum):
    """
    Action to take when handling an exception.
    
    Uses IntEnum for performance - exception handling is a hot path.
    """
    RAISE_ORIGINAL = 0      # Re-raise original exception as-is (most common)
    RAISE_TRANSFORMED = 1   # Transform and raise different exception
    SUPPRESS = 2            # Don't raise, return default value
    FALLBACK = 3            # Use fallback value


class ResilienceError(Exception):
    """
    Base exception for all aioresilience pattern-raised errors.
    
    Provides rich context about the pattern that raised it.
    
    Attributes:
        message: Error message
        pattern_name: Name of the pattern instance
        pattern_type: Type of pattern (circuit_breaker, bulkhead, etc.)
        reason: Reason code (IntEnum specific to pattern)
        metadata: Additional context information
    """
    
    def __init__(
        self,
        message: str,
        pattern_name: Optional[str] = None,
        pattern_type: Optional[str] = None,
        reason: Optional[IntEnum] = None,
        **metadata
    ):
        super().__init__(message)
        self.pattern_name = pattern_name
        self.pattern_type = pattern_type
        self.reason = reason
        self.metadata = metadata
    
    def __repr__(self):
        parts = [f"{self.__class__.__name__}('{str(self)}')"]
        if self.pattern_name:
            parts.append(f"pattern_name='{self.pattern_name}'")
        if self.reason is not None:
            parts.append(f"reason={self.reason.name if hasattr(self.reason, 'name') else self.reason}")
        return f"<{', '.join(parts)}>"


@dataclass
class ExceptionContext:
    """
    Context information passed to exception transformers and handlers.
    
    Contains all relevant information about the exception occurrence,
    including pattern details and metadata.
    
    Attributes:
        pattern_name: Name of the pattern instance
        pattern_type: Type of pattern (circuit_breaker, bulkhead, timeout, etc.)
        reason: Reason code (IntEnum) why exception is being raised
        original_exception: The original exception (if any)
        metadata: Additional context data
    """
    pattern_name: str
    pattern_type: str
    reason: IntEnum
    original_exception: Optional[Exception] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert context to dictionary for logging/debugging"""
        return {
            "pattern_name": self.pattern_name,
            "pattern_type": self.pattern_type,
            "reason": self.reason.name if hasattr(self.reason, "name") else str(self.reason),
            "original_exception": str(self.original_exception) if self.original_exception else None,
            "metadata": self.metadata,
        }
