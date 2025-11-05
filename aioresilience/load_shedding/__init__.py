"""
Load Shedding Module

Provides load shedding based on request count (basic) or system metrics (CPU/memory).

Default import provides BasicLoadShedder:
    from aioresilience import LoadShedder  # BasicLoadShedder

Explicit imports:
    from aioresilience.load_shedding import BasicLoadShedder, SystemLoadShedder
"""

from .basic import BasicLoadShedder, LoadLevel, LoadMetrics, with_load_shedding

# Try to import SystemLoadShedder, but don't fail if psutil is not installed
try:
    from .system import SystemLoadShedder
    _has_psutil = True
except ImportError:
    _has_psutil = False
    
    class SystemLoadShedder:
        """Placeholder for SystemLoadShedder when psutil is not installed."""
        
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "SystemLoadShedder requires the 'psutil' package. "
                "Install it with: pip install aioresilience[system]"
            )

# Default alias
LoadShedder = BasicLoadShedder

__all__ = [
    "BasicLoadShedder",
    "SystemLoadShedder",
    "LoadShedder",  # Alias for BasicLoadShedder
    "LoadLevel",
    "LoadMetrics",
    "with_load_shedding",
]
