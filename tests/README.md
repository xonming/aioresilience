# Test Suite Organization

**Coverage: 87.6%+** | **309 Tests Passing** | **1 Skip** (Optional Dependency)

## Test Structure

```
tests/
├── unit/                           # Unit tests (isolated)
│   ├── test_circuit_breaker.py
│   ├── test_retry.py
│   ├── test_timeout.py
│   ├── test_bulkhead.py
│   ├── test_fallback.py
│   ├── test_backpressure.py
│   ├── test_adaptive_concurrency.py
│   ├── test_rate_limiting.py
│   └── test_load_shedding.py
│
├── mocked/                         # Tests with mocked dependencies
│   ├── test_redis_rate_limiting.py
│   └── test_system_load_shedding.py
│
├── integration/                    # Integration tests
│   ├── test_pattern_combinations.py
│   ├── test_fastapi_integration.py
│   ├── test_sanic_integration.py
│   └── test_aiohttp_integration.py
│
├── stress/                         # Concurrency & performance tests
│   ├── test_high_concurrency.py
│   └── test_performance.py
│
└── README.md                       # This file

## Test Categories

### Unit Tests
- Individual pattern tests with no external dependencies
- State machine testing (circuit breaker states)
- Algorithm verification (backoff strategies, AIMD)
- Edge case handling

### Mocked Tests
- Redis rate limiting with fakeredis/mocks
- System metrics (psutil) mocking
- External dependency isolation

### Integration Tests
- Pattern combinations (stacking decorators)
- Framework middleware end-to-end
- Multi-pattern workflows

### Stress Tests
- High concurrency scenarios (1000+ requests)
- Performance benchmarks
- Memory profiling
- Throughput measurements

## Running Tests

```bash
# All unit tests
pytest tests/unit/

# All integration tests  
pytest tests/integration/

# Specific test file
pytest tests/unit/test_circuit_breaker.py

# With coverage
pytest tests/unit/ --cov=aioresilience --cov-report=html

# Parallel execution (faster)
pytest tests/unit/ -n auto

# Verbose output
pytest tests/unit/ -v
```
