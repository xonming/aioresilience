"""
Event emitter for individual resilience patterns
"""

import asyncio
from typing import Dict, List, Callable, Union
from .types import ResilienceEvent
from ..logging import log_error


class EventEmitter:
    """
    Event emitter for individual patterns
    Auto-forwards events to global bus when it's active
    """
    
    # Class variable - shared across all instances
    _global_bus_enabled = False
    _global_bus = None
    
    def __init__(self, pattern_name: str):
        """
        Initialize event emitter
        
        Args:
            pattern_name: Name of the pattern instance
        """
        self.pattern_name = pattern_name
        
        # event_type (str or int) -> List[handler]
        self._handlers: Dict[Union[str, int], List[Callable]] = {}
        
        # Wildcard handlers (listen to all events from this pattern)
        self._wildcard: List[Callable] = []
    
    def on(self, event_type: Union[str, int]):
        """
        Register an event handler (decorator style)
        
        Args:
            event_type: Event type to listen for (string name, int value, or "*" for all events)
        
        Usage:
            @circuit.events.on(EventType.RETRY_EXHAUSTED.value)  # Efficient
            async def handler(event):
                ...
        """
        def decorator(handler: Callable):
            self.add_handler(event_type, handler)
            return handler
        return decorator
    
    def add_handler(self, event_type: Union[str, int], handler: Callable):
        """
        Add handler programmatically (non-decorator style)
        
        Args:
            event_type: Event type to listen for (string name, int value, or "*" for all events)
            handler: Async callable that receives ResilienceEvent
        """
        if event_type == "*":
            self._wildcard.append(handler)
        else:
            if event_type not in self._handlers:
                self._handlers[event_type] = []
            self._handlers[event_type].append(handler)
    
    def remove_handler(self, event_type: Union[str, int], handler: Callable):
        """
        Remove a handler
        
        Args:
            event_type: Event type the handler is registered for (string or int)
            handler: Handler to remove
        """
        try:
            if event_type == "*":
                self._wildcard.remove(handler)
            else:
                self._handlers[event_type].remove(handler)
        except (ValueError, KeyError):
            pass  # Handler not found, ignore
    
    def has_listeners(self) -> bool:
        """
        Check if there are any event listeners registered (performance optimization)
        
        Returns:
            True if any handlers are registered (local or global)
        """
        has_local = bool(self._handlers or self._wildcard)
        has_global = EventEmitter._global_bus_enabled
        return has_local or has_global
    
    async def emit(self, event: ResilienceEvent):
        """
        Emit an event to all registered handlers (local and global)
        
        Args:
            event: ResilienceEvent to emit
        """
        # Fast path: check if any handlers exist at all
        # Support both enum value (int) and enum name (string) lookups
        handlers_by_value = self._handlers.get(event.event_type.value, [])
        handlers_by_name = self._handlers.get(event.event_type.name.lower(), [])
        local_handlers = handlers_by_value + handlers_by_name
        has_local = bool(local_handlers or self._wildcard)
        has_global = EventEmitter._global_bus_enabled
        
        if not has_local and not has_global:
            return  # No handlers, exit immediately
        
        # Fast path: single local handler, no global, no wildcard
        if not has_global and len(local_handlers) == 1 and not self._wildcard:
            try:
                await local_handlers[0](event)
            except Exception as e:
                # Log handler errors but don't propagate to prevent cascading failures
                log_error(
                    f'aioresilience.events.{self.pattern_name}',
                    e,
                    event_type=event.event_type.value,
                    handler_count=1
                )
            return
        
        # Combine local and global handlers into single gather call
        if has_global:
            # Lazy load global bus if not already cached
            if EventEmitter._global_bus is None:
                from .bus import global_bus
                EventEmitter._global_bus = global_bus
            
            # Get global bus handlers directly (avoid double dispatch)
            # Support both enum value and enum name lookups
            global_handlers_by_value = EventEmitter._global_bus._handlers.get(event.event_type.value, [])
            global_handlers_by_name = EventEmitter._global_bus._handlers.get(event.event_type.name.lower(), [])
            global_handlers = global_handlers_by_value + global_handlers_by_name
            global_wildcard = EventEmitter._global_bus._wildcard
            
            total_handlers = len(local_handlers) + len(self._wildcard) + len(global_handlers) + len(global_wildcard)
            
            if total_handlers > 0:
                # Use generator expressions directly - avoids intermediate list allocation
                await asyncio.gather(
                    *(self._safe_call(h, event) for h in local_handlers),
                    *(self._safe_call(h, event) for h in self._wildcard),
                    *(self._safe_call(h, event) for h in global_handlers),
                    *(self._safe_call(h, event) for h in global_wildcard)
                )
        else:
            # No global bus - just local handlers
            await asyncio.gather(
                *(self._safe_call(h, event) for h in local_handlers),
                *(self._safe_call(h, event) for h in self._wildcard)
            )
    
    async def _safe_call(self, handler: Callable, event: ResilienceEvent):
        """Safely call handler with error handling"""
        try:
            await handler(event)
        except Exception as e:
            # Log handler errors but don't propagate to prevent cascading failures
            log_error(
                f'aioresilience.events.{self.pattern_name}',
                e,
                handler=getattr(handler, '__name__', 'unknown'),
                event_type=event.event_type.value
            )
    
    def clear(self):
        """Remove all local handlers"""
        self._handlers.clear()
        self._wildcard.clear()
    
    @property
    def handler_count(self) -> int:
        """Get number of local handlers registered"""
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
    
    @classmethod
    def is_global_bus_enabled(cls) -> bool:
        """Check if global bus is enabled"""
        return cls._global_bus_enabled
    
    @classmethod
    def get_global_bus(cls):
        """Get the global bus instance"""
        if cls._global_bus is None:
            from .bus import global_bus
            cls._global_bus = global_bus
        return cls._global_bus
