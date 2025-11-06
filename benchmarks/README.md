# Benchmark Suite

This directory contains performance benchmarks for aioresilience patterns.

## Running Benchmarks

```bash
# Run all benchmarks with default settings
python benchmarks/benchmark_concurrent.py

# Run with more iterations
python benchmarks/benchmark_concurrent.py --iterations 100000 --runs 10

# Run specific patterns
python benchmarks/benchmark_concurrent.py --patterns circuit_breaker,bulkhead,retry

# Run with failure injection
python benchmarks/benchmark_concurrent.py --with-failures

# Run contention tests only
python benchmarks/benchmark_concurrent.py --contention-only

# Test event system overhead (local handlers)
python benchmarks/benchmark_concurrent.py --with-events

# Test event system with global bus
python benchmarks/benchmark_concurrent.py --global-events

# Combined: events + failures
python benchmarks/benchmark_concurrent.py --with-events --with-failures
```

## Benchmark Types

### 1. Concurrent Overhead
Measures overhead under concurrent load using asyncio.gather:
- Low Contention: High limits, no queuing/blocking
- High Contention: Realistic limits with queuing and rejections
- Failure Modes: Random exceptions, timeouts, and error handling

### 2. Sequential Overhead
Simple sequential execution to measure minimum overhead.

## Interpreting Results

### What to Look For

**Overhead per Operation:**
- **Excellent**: <10 µs/op - Suitable for high-throughput APIs (>50k RPS)
- **Good**: 10-50 µs/op - Production ready for most use cases (>20k RPS)
- **Acceptable**: 50-200 µs/op - Fine for moderate load (<10k RPS)
- **High**: >200 µs/op - May indicate contention or need optimization

**Throughput:**
- Measure operations per second
- Compare baseline vs. pattern overhead
- Look for patterns that don't scale linearly under contention

**Variability (Stddev):**
- Low (<10% of mean): Consistent performance
- High (>50% of mean): May indicate GC pauses, system contention, or locks

### Design Goals

aioresilience aims for:
- Microsecond-level overhead per operation
- Minimal allocations and GC pressure
- Lock-free designs where possible
- Support for 20,000+ RPS in production APIs

## Sharing Results

When sharing benchmark results, include:

**System Info:**
- CPU model and cores
- RAM size
- OS and version
- Python version
- asyncio event loop (default vs uvloop)

**Example:**
```
System: Intel i7-12700K (12 cores), 32GB RAM, Ubuntu 22.04
Python: 3.12.0 with uvloop
Results: Baseline 0.5 µs/op, Circuit Breaker 5.2 µs/op
```
