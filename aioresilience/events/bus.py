"""
Global event bus for centralized monitoring
"""

import asyncio
from typing import Dict, List, Callable
from .types import ResilienceEvent
from ..logging import log_error


class GlobalEventBus:
    """
    Global event bus for monitoring all resilience patterns
    Automatically enables when first handler is registered (lazy initialization)
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # event_type -> List[handler]
        self._handlers: Dict[str, List[Callable]] = {}
        
        # Wildcard handlers (listen to all events)
        self._wildcard: List[Callable] = []
        
        # Flag to track if bus is active
        self._active = False
        
        self._initialized = True
    
    def on(self, event_type: str):
        """
        Register an event handler (decorator style)
        Auto-enables global bus on first handler registration
        
        Args:
            event_type: Event type to listen for, or "*" for all events
        
        Usage:
            @global_bus.on("state_change")
            async def handler(event):
                ...
        """
        def decorator(handler: Callable):
            # Auto-enable on first handler registration
            if not self._active:
                self._active = True
                # Enable forwarding in EventEmitter
                from .emitter import EventEmitter
                EventEmitter._global_bus_enabled = True
            
            if event_type == "*":
                self._wildcard.append(handler)
            else:
                if event_type not in self._handlers:
                    self._handlers[event_type] = []
                self._handlers[event_type].append(handler)
            
            return handler
        return decorator
    
    def add_handler(self, event_type: str, handler: Callable):
        """
        Add handler programmatically (non-decorator style)
        
        Args:
            event_type: Event type to listen for, or "*" for all events
            handler: Async callable that receives ResilienceEvent
        """
        # Auto-enable
        if not self._active:
            self._active = True
            from .emitter import EventEmitter
            EventEmitter._global_bus_enabled = True
        
        if event_type == "*":
            self._wildcard.append(handler)
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
    
    def remove_handler(self, event_type: str, handler: Callable):
        """Remove a handler"""
        try:
            if event_type == "*":
                self._wildcard.remove(handler)
            else:
                self._handlers[event_type].remove(handler)
        except (ValueError, KeyError):
            pass  # Handler not found, ignore
    
    async def emit(self, event: ResilienceEvent):
        """
        Emit an event to all registered handlers
        
        Args:
            event: ResilienceEvent to emit
        """
        if not self._active:
            return  # No handlers registered, skip
        
        # Get handlers for this event type
        event_handlers = self._handlers.get(event.event_type.value, [])
        
        # Fast path: no handlers at all
        if not event_handlers and not self._wildcard:
            return
        
        # Fast path: single handler, no wildcard - direct await is faster
        if not self._wildcard and len(event_handlers) == 1:
            try:
                await event_handlers[0](event)
            except Exception as e:
                # Log handler errors but don't propagate to prevent cascading failures
                log_error(
                    'aioresilience.events.global_bus',
                    e,
                    event_type=event.event_type.value,
                    handler_count=1
                )
            return
        
        # Use generator expressions directly - avoids intermediate list allocation
        await asyncio.gather(
            *(self._safe_call(h, event) for h in event_handlers),
            *(self._safe_call(h, event) for h in self._wildcard)
        )
    
    async def _safe_call(self, handler: Callable, event: ResilienceEvent):
        """Safely call handler with error handling"""
        try:
            await handler(event)
        except Exception as e:
            # Log handler errors but don't propagate to prevent cascading failures
            log_error(
                'aioresilience.events.global_bus',
                e,
                handler=getattr(handler, '__name__', 'unknown'),
                event_type=event.event_type.value
            )
    
    def clear(self):
        """Remove all handlers and deactivate bus"""
        self._handlers.clear()
        self._wildcard.clear()
        self._active = False
        
        # Disable forwarding
        from .emitter import EventEmitter
        EventEmitter._global_bus_enabled = False
    
    @property
    def is_active(self) -> bool:
        """Check if global bus has any handlers registered"""
        return self._active
    
    @property
    def handler_count(self) -> int:
        """Get total number of registered handlers"""
        return sum(len(h) for h in self._handlers.values()) + len(self._wildcard)
    
    def get_handlers(self, event_type: str = None) -> int:
        """
        Get number of handlers for a specific event type
        
        Args:
            event_type: Event type to check, or None for total count
        
        Returns:
            Number of handlers
        """
        if event_type is None:
            return self.handler_count
        elif event_type == "*":
            return len(self._wildcard)
        else:
            return len(self._handlers.get(event_type, []))


# Global singleton instance
global_bus = GlobalEventBus()
