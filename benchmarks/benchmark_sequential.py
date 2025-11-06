#!/usr/bin/env python3
"""
Sequential Overhead Benchmark for aioresilience

Measures minimum overhead of resilience patterns with sequential execution.
Useful for baseline comparison and identifying per-operation costs.

Usage:
    python benchmark_sequential.py
    python benchmark_sequential.py --iterations 100000
"""

import asyncio
import argparse
import statistics
import time
from typing import Callable

from aioresilience import (
    CircuitBreaker,
    RetryPolicy,
    RetryStrategy,
    TimeoutManager,
    Bulkhead,
    FallbackHandler,
    RateLimiter,
    LoadShedder,
    BackpressureManager,
    AdaptiveConcurrencyLimiter,
)


DEFAULT_ITERATIONS = 50000
DEFAULT_RUNS = 5


async def noop():
    """Baseline no-op function"""
    pass


async def run_sequential_benchmark(
    name: str,
    func: Callable,
    iterations: int,
    runs: int
) -> dict:
    """Run benchmark sequentially and collect statistics"""
    times = []
    
    for run in range(runs):
        start = time.perf_counter()
        for _ in range(iterations):
            await func()
        end = time.perf_counter()
        times.append(end - start)
    
    mean_time = statistics.mean(times)
    
    return {
        'name': name,
        'mean_total': mean_time,
        'stddev': statistics.stdev(times) if len(times) > 1 else 0,
        'min': min(times),
        'max': max(times),
        'per_op_us': (mean_time / iterations) * 1_000_000,
        'ops_per_sec': iterations / mean_time,
    }


async def main():
    parser = argparse.ArgumentParser(description='Sequential benchmark for aioresilience')
    parser.add_argument('--iterations', type=int, default=DEFAULT_ITERATIONS,
                       help='Iterations per run')
    parser.add_argument('--runs', type=int, default=DEFAULT_RUNS,
                       help='Number of runs for statistics')
    
    args = parser.parse_args()
    
    print(f"\naioresilience Sequential Overhead Benchmark")
    print(f"{'='*100}")
    print(f"Iterations per run: {args.iterations:,}")
    print(f"Runs for statistics: {args.runs}")
    print(f"Total operations: {args.iterations * args.runs:,}")
    print(f"Execution: Sequential (for loop)")
    
    results = []
    
    # Baseline
    print("\nRunning baseline...")
    baseline = await run_sequential_benchmark(
        "Baseline (no pattern)", noop, args.iterations, args.runs
    )
    results.append(baseline)
    
    # Circuit Breaker
    print("Running Circuit Breaker...")
    cb = CircuitBreaker(name="bench", failure_threshold=100000)
    results.append(await run_sequential_benchmark(
        "Circuit Breaker",
        lambda: cb.call(noop),
        args.iterations,
        args.runs
    ))
    
    # Retry
    print("Running Retry...")
    retry = RetryPolicy(max_attempts=1, initial_delay=0.001, strategy=RetryStrategy.CONSTANT)
    results.append(await run_sequential_benchmark(
        "Retry (1 attempt)",
        lambda: retry.execute(noop),
        args.iterations,
        args.runs
    ))
    
    # Timeout
    print("Running Timeout...")
    timeout_mgr = TimeoutManager(timeout=10.0)
    results.append(await run_sequential_benchmark(
        "Timeout",
        lambda: timeout_mgr.execute(noop),
        args.iterations,
        args.runs
    ))
    
    # Bulkhead
    print("Running Bulkhead...")
    bulkhead = Bulkhead(max_concurrent=100000, max_waiting=0)
    results.append(await run_sequential_benchmark(
        "Bulkhead",
        lambda: bulkhead.execute(noop),
        args.iterations,
        args.runs
    ))
    
    # Fallback
    print("Running Fallback...")
    fallback = FallbackHandler(fallback="fallback")
    results.append(await run_sequential_benchmark(
        "Fallback",
        lambda: fallback.execute(noop),
        args.iterations,
        args.runs
    ))
    
    # Rate Limiter
    print("Running Rate Limiter...")
    limiter = RateLimiter(name="bench")
    results.append(await run_sequential_benchmark(
        "Rate Limiter",
        lambda: limiter.check_rate_limit("user_1", "100000/second"),
        args.iterations,
        args.runs
    ))
    
    # Load Shedder
    print("Running Load Shedder...")
    shedder = LoadShedder(max_requests=100000)
    
    async def load_shed_test():
        if await shedder.acquire():
            try:
                await noop()
            finally:
                await shedder.release()
    
    results.append(await run_sequential_benchmark(
        "Load Shedder",
        load_shed_test,
        args.iterations,
        args.runs
    ))
    
    # Backpressure
    print("Running Backpressure...")
    bp = BackpressureManager(max_pending=100000, high_water_mark=90000)
    
    async def backpressure_test():
        if await bp.acquire():
            try:
                await noop()
            finally:
                await bp.release()
    
    results.append(await run_sequential_benchmark(
        "Backpressure",
        backpressure_test,
        args.iterations,
        args.runs
    ))
    
    # Adaptive Concurrency
    print("Running Adaptive Concurrency...")
    adaptive = AdaptiveConcurrencyLimiter(initial_limit=10000, min_limit=10, max_limit=100000)
    
    async def adaptive_test():
        if await adaptive.acquire():
            try:
                await noop()
                await adaptive.release(success=True)
            except:
                await adaptive.release(success=False)
    
    results.append(await run_sequential_benchmark(
        "Adaptive Concurrency",
        adaptive_test,
        args.iterations,
        args.runs
    ))
    
    # Print results
    print(f"\n{'='*100}")
    print(f"{'Pattern':<25} {'Time/Op (µs)':<15} {'Ops/Sec':<15} {'Net OH (µs)':<15} {'Stddev (ms)':<12}")
    print(f"{'='*100}")
    
    baseline_per_op = baseline['per_op_us']
    
    for result in results:
        net_overhead = result['per_op_us'] - baseline_per_op
        print(
            f"{result['name']:<25} "
            f"{result['per_op_us']:>12.2f}   "
            f"{result['ops_per_sec']:>12.0f}   "
            f"{net_overhead:>12.2f}   "
            f"{result['stddev']*1000:>10.2f}"
        )
    
    print(f"{'='*100}\n")
    
    # Key insights
    max_overhead = max(r['per_op_us'] - baseline_per_op for r in results[1:])
    avg_overhead = statistics.mean([r['per_op_us'] - baseline_per_op for r in results[1:]])
    
    print("\nKEY INSIGHTS:")
    print(f"- Baseline overhead: {baseline_per_op:.2f} µs/op ({baseline['ops_per_sec']:.0f} ops/sec)")
    print(f"- Average pattern overhead: {avg_overhead:.2f} µs/op")
    print(f"- Maximum pattern overhead: {max_overhead:.2f} µs/op")
    print(f"- Sequential execution shows minimum theoretical overhead")
    print(f"- Compare with concurrent benchmarks to see parallelism impact")
    print(f"\n{'='*100}\n")


if __name__ == "__main__":
    asyncio.run(main())
