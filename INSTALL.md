# Installation Guide

## Basic Installation

Install the core package:

```bash
pip install aioresilience
```

## Optional Dependencies

### Redis Support (Distributed Rate Limiting)

```bash
# Using pip extras
pip install aioresilience[redis]

# Or using requirements file
pip install -r requirements-redis.txt
```

### System Monitoring (Load Shedding with CPU/Memory)

```bash
# Using pip extras
pip install aioresilience[system]

# Or using requirements file
pip install -r requirements-system.txt
```

### Framework Integrations

#### FastAPI

```bash
# Using pip extras
pip install aioresilience[fastapi]
```

#### Sanic

```bash
# Using pip extras
pip install aioresilience[sanic]
```

#### aiohttp

```bash
# Using pip extras
pip install aioresilience[aiohttp]
```

#### All Integrations

```bash
# Using pip extras
pip install aioresilience[integrations]

# Or using requirements file
pip install -r requirements-integrations.txt
```

### All Optional Dependencies

```bash
# Using pip extras
pip install aioresilience[all]

# Or using requirements file
pip install -r requirements-all.txt
```

## Development Installation

For development work:

```bash
# Clone the repository
git clone https://github.com/xonming/aioresilience.git
cd aioresilience

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Or using requirements file
pip install -r requirements-dev.txt
```

## Requirements Files Summary

| File | Purpose |
|------|---------|
| `requirements.txt` | Core dependencies only |
| `requirements-dev.txt` | Development and testing dependencies |
| `requirements-redis.txt` | Redis support |
| `requirements-system.txt` | System monitoring support |
| `requirements-integrations.txt` | All framework integrations |
| `requirements-all.txt` | All optional dependencies |

## Extras Summary

| Extra | Description | Install Command |
|-------|-------------|-----------------|
| `redis` | Redis-backed rate limiting | `pip install aioresilience[redis]` |
| `system` | System monitoring (CPU/Memory) | `pip install aioresilience[system]` |
| `fastapi` | FastAPI integration | `pip install aioresilience[fastapi]` |
| `sanic` | Sanic integration | `pip install aioresilience[sanic]` |
| `aiohttp` | aiohttp integration | `pip install aioresilience[aiohttp]` |
| `integrations` | All framework integrations | `pip install aioresilience[integrations]` |
| `dev` | Development dependencies | `pip install aioresilience[dev]` |
| `all` | All optional dependencies | `pip install aioresilience[all]` |

## Minimal Installation Examples

### Just Circuit Breaker and Retry

```bash
pip install aioresilience
```

No additional dependencies needed!

### With Distributed Rate Limiting

```bash
pip install aioresilience[redis]
```

### With FastAPI Integration

```bash
pip install aioresilience[fastapi]
```

### Full Stack (All Features)

```bash
pip install aioresilience[all]
```

## Verifying Installation

```python
import aioresilience
print(aioresilience.__version__)

# Check what's available
from aioresilience import (
    CircuitBreaker,
    RateLimiter,
    LoadShedder,
    Bulkhead,
    RetryPolicy,
    TimeoutManager,
    FallbackHandler,
)
```

## Troubleshooting

### ImportError for optional dependencies

If you see:
```
ModuleNotFoundError: No module named 'redis'
```

Install the redis extra:
```bash
pip install aioresilience[redis]
```

### Testing Framework Integrations

For running integration tests:
```bash
pip install aioresilience[dev]
```

This installs all framework dependencies needed for testing.
