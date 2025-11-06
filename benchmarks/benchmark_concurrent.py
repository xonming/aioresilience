#!/usr/bin/env python3
"""
Concurrent Overhead Benchmark for aioresilience

Measures overhead of resilience patterns under concurrent load using asyncio.gather.
Tests both low-contention (unlimited limits) and high-contention (realistic limits) scenarios.

Usage:
    python benchmark_concurrent.py
    python benchmark_concurrent.py --iterations 100000 --runs 10
    python benchmark_concurrent.py --with-failures
"""

import asyncio
import argparse
import random
import statistics
import time
from typing import Callable, Any

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
    global_bus,
)


# Benchmark configuration
DEFAULT_ITERATIONS = 10000
DEFAULT_RUNS = 5
DEFAULT_CONTENTION_ITERATIONS = 5000


class BenchmarkRunner:
    """Runs and reports benchmark results"""
    
    def __init__(self, iterations: int = DEFAULT_ITERATIONS, runs: int = DEFAULT_RUNS):
        self.iterations = iterations
        self.runs = runs
        self.results = {}
    
    async def run_benchmark(
        self,
        name: str,
        func: Callable,
        *args,
        **kwargs
    ) -> dict[str, float]:
        """Run a benchmark multiple times and collect statistics"""
        times = []
        
        for run in range(self.runs):
            start = time.perf_counter()
            await asyncio.gather(*[func(*args, **kwargs) for _ in range(self.iterations)])
            end = time.perf_counter()
            times.append(end - start)
        
        total_ops = self.iterations * self.runs
        mean_time = statistics.mean(times)
        
        return {
            'name': name,
            'mean_total': mean_time,
            'stddev': statistics.stdev(times) if len(times) > 1 else 0,
            'min': min(times),
            'max': max(times),
            'per_op_us': (mean_time / self.iterations) * 1_000_000,
            'ops_per_sec': self.iterations / mean_time,
        }
    
    def print_results(self, results: list[dict], baseline: dict = None):
        """Print formatted results table"""
        print(f"\n{'='*100}")
        print(f"{'Pattern':<25} {'Time/Op (µs)':<15} {'Ops/Sec':<15} {'Net OH (µs)':<15} {'Stddev (ms)':<12}")
        print(f"{'='*100}")
        
        baseline_per_op = baseline['per_op_us'] if baseline else 0
        
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


# Test functions
async def noop():
    """Baseline no-op function"""
    pass


async def noop_with_failure(failure_rate: float = 0.1):
    """No-op with random failures"""
    if random.random() < failure_rate:
        raise ValueError("Simulated failure")


async def noop_slow():
    """No-op with small delay to simulate I/O"""
    await asyncio.sleep(0.001)


# Global event handlers for benchmarking
_event_counter = 0

async def _global_event_handler(event):
    """Simple global event handler that increments counter"""
    global _event_counter
    _event_counter += 1

async def _local_event_handler(event):
    """Simple local event handler that increments counter"""
    global _event_counter
    _event_counter += 1


# Pattern benchmark functions
async def benchmark_circuit_breaker(with_failures: bool = False, with_events: bool = False):
    """Benchmark CircuitBreaker"""
    cb = CircuitBreaker(name="bench", failure_threshold=100000, timeout=None)
    
    if with_events:
        # Attach local event handler
        cb.events.on("call_success")(_local_event_handler)
        cb.events.on("call_failure")(_local_event_handler)
    
    func = noop_with_failure if with_failures else noop
    try:
        await cb.call(func)
    except Exception:
        pass


async def benchmark_retry(with_failures: bool = False, with_events: bool = False):
    """Benchmark RetryPolicy"""
    policy = RetryPolicy(
        max_attempts=3 if with_failures else 1,
        initial_delay=0.001,
        strategy=RetryStrategy.CONSTANT,
    )
    
    if with_events:
        policy.events.on("retry_success")(_local_event_handler)
        policy.events.on("retry_attempt")(_local_event_handler)
    
    func = noop_with_failure if with_failures else noop
    try:
        await policy.execute(func)
    except Exception:
        pass


async def benchmark_timeout(with_timeout: bool = False, with_events: bool = False):
    """Benchmark TimeoutManager"""
    manager = TimeoutManager(timeout=0.01 if with_timeout else 10.0)
    
    if with_events:
        manager.events.on("timeout_success")(_local_event_handler)
        manager.events.on("timeout_occurred")(_local_event_handler)
    
    func = noop_slow if with_timeout else noop
    try:
        await manager.execute(func)
    except Exception:
        pass


async def benchmark_bulkhead(contention: bool = False, with_events: bool = False):
    """Benchmark Bulkhead"""
    max_concurrent = 100 if contention else 100000
    bulkhead = Bulkhead(max_concurrent=max_concurrent, max_waiting=0, timeout=0.01)
    
    if with_events:
        bulkhead.events.on("slot_acquired")(_local_event_handler)
        bulkhead.events.on("slot_released")(_local_event_handler)
    
    func = noop_slow if contention else noop
    try:
        await bulkhead.execute(func)
    except Exception:
        pass


async def benchmark_fallback(with_failures: bool = False, with_events: bool = False):
    """Benchmark FallbackHandler"""
    fallback = FallbackHandler(fallback="fallback")
    
    if with_events:
        fallback.events.on("primary_failed")(_local_event_handler)
        fallback.events.on("fallback_executed")(_local_event_handler)
    
    func = noop_with_failure if with_failures else noop
    await fallback.execute(func)


async def benchmark_rate_limiter():
    """Benchmark RateLimiter"""
    limiter = RateLimiter(name="bench")
    key = f"user_{random.randint(1, 1000)}"
    await limiter.check_rate_limit(key, "100000/second")


async def benchmark_load_shedder(contention: bool = False, with_events: bool = False):
    """Benchmark LoadShedder"""
    max_requests = 100 if contention else 100000
    shedder = LoadShedder(max_requests=max_requests)
    
    if with_events:
        shedder.events.on("request_accepted")(_local_event_handler)
        shedder.events.on("request_shed")(_local_event_handler)
    
    func = noop_slow if contention else noop
    if await shedder.acquire():
        try:
            await func()
        finally:
            await shedder.release()


async def benchmark_backpressure(contention: bool = False, with_events: bool = False):
    """Benchmark BackpressureManager"""
    max_pending = 100 if contention else 100000
    bp = BackpressureManager(max_pending=max_pending, high_water_mark=max_pending-10)
    
    if with_events:
        bp.events.on("threshold_exceeded")(_local_event_handler)
        bp.events.on("load_level_change")(_local_event_handler)
    
    func = noop_slow if contention else noop
    if await bp.acquire(timeout=0.01 if contention else None):
        try:
            await func()
        finally:
            await bp.release()


async def benchmark_adaptive_concurrency(contention: bool = False, with_events: bool = False):
    """Benchmark AdaptiveConcurrencyLimiter"""
    limiter = AdaptiveConcurrencyLimiter(
        initial_limit=100 if contention else 10000,
        min_limit=10,
        max_limit=100000,
    )
    
    if with_events:
        limiter.events.on("load_level_change")(_local_event_handler)
    
    func = noop_slow if contention else noop
    if await limiter.acquire():
        try:
            await func()
            await limiter.release(success=True)
        except Exception:
            await limiter.release(success=False)


async def main():
    """Run all benchmarks"""
    parser = argparse.ArgumentParser(description='Benchmark aioresilience patterns')
    parser.add_argument('--iterations', type=int, default=DEFAULT_ITERATIONS,
                       help='Iterations per run')
    parser.add_argument('--runs', type=int, default=DEFAULT_RUNS,
                       help='Number of runs for statistics')
    parser.add_argument('--with-failures', action='store_true',
                       help='Include failure injection tests')
    parser.add_argument('--contention-only', action='store_true',
                       help='Run only contention tests')
    parser.add_argument('--patterns', type=str, default='',
                       help='Comma-separated list of patterns to test')
    parser.add_argument('--with-events', action='store_true',
                       help='Include event system overhead in benchmarks')
    parser.add_argument('--global-events', action='store_true',
                       help='Test with global event bus (use with --with-events)')
    
    args = parser.parse_args()
    
    runner = BenchmarkRunner(iterations=args.iterations, runs=args.runs)
    
    # Setup global event bus if requested
    if args.global_events:
        args.with_events = True  # Implies with_events
        global_bus.on("*")(_global_event_handler)
        print("\n⚠️  Global event bus handler attached (will capture ALL events)")
    
    print(f"\naioresilience Concurrent Overhead Benchmark")
    print(f"{'='*100}")
    print(f"Iterations per run: {args.iterations:,}")
    print(f"Runs for statistics: {args.runs}")
    print(f"Total operations: {args.iterations * args.runs:,}")
    print(f"Concurrency: asyncio.gather with {args.iterations} tasks")
    if args.with_events:
        print(f"Event System: {'Global Bus' if args.global_events else 'Local Handlers'} - Enabled")
    else:
        print(f"Event System: Disabled (use --with-events to test)")
    
    # Filter patterns if specified
    selected_patterns = args.patterns.split(',') if args.patterns else []
    
    def should_run(pattern_name: str) -> bool:
        if not selected_patterns:
            return True
        return any(p.strip() in pattern_name.lower() for p in selected_patterns)
    
    if not args.contention_only:
        print(f"\n\n{'#'*100}")
        print("# LOW CONTENTION - Unlimited Limits (Measuring Base Overhead)")
        print(f"{'#'*100}")
        
        results = []
        
        # Baseline
        print("\nRunning baseline...")
        baseline = await runner.run_benchmark("Baseline (no pattern)", noop)
        results.append(baseline)
        
        # Patterns
        if should_run('circuit_breaker'):
            print("Running Circuit Breaker...")
            name_suffix = " +events" if args.with_events else ""
            results.append(await runner.run_benchmark(
                f"Circuit Breaker{name_suffix}", benchmark_circuit_breaker, False, args.with_events
            ))
        
        if should_run('retry'):
            print("Running Retry...")
            name_suffix = " +events" if args.with_events else ""
            results.append(await runner.run_benchmark(
                f"Retry (no failures){name_suffix}", benchmark_retry, False, args.with_events
            ))
        
        if should_run('timeout'):
            print("Running Timeout...")
            name_suffix = " +events" if args.with_events else ""
            results.append(await runner.run_benchmark(
                f"Timeout{name_suffix}", benchmark_timeout, False, args.with_events
            ))
        
        if should_run('bulkhead'):
            print("Running Bulkhead...")
            name_suffix = " +events" if args.with_events else ""
            results.append(await runner.run_benchmark(
                f"Bulkhead{name_suffix}", benchmark_bulkhead, False, args.with_events
            ))
        
        if should_run('fallback'):
            print("Running Fallback...")
            name_suffix = " +events" if args.with_events else ""
            results.append(await runner.run_benchmark(
                f"Fallback (no failures){name_suffix}", benchmark_fallback, False, args.with_events
            ))
        
        if should_run('rate'):
            print("Running Rate Limiter...")
            results.append(await runner.run_benchmark(
                "Rate Limiter", benchmark_rate_limiter
            ))
        
        if should_run('load'):
            print("Running Load Shedder...")
            name_suffix = " +events" if args.with_events else ""
            results.append(await runner.run_benchmark(
                f"Load Shedder{name_suffix}", benchmark_load_shedder, False, args.with_events
            ))
        
        if should_run('backpressure'):
            print("Running Backpressure...")
            name_suffix = " +events" if args.with_events else ""
            results.append(await runner.run_benchmark(
                f"Backpressure{name_suffix}", benchmark_backpressure, False, args.with_events
            ))
        
        if should_run('adaptive'):
            print("Running Adaptive Concurrency...")
            name_suffix = " +events" if args.with_events else ""
            results.append(await runner.run_benchmark(
                f"Adaptive Concurrency{name_suffix}", benchmark_adaptive_concurrency, False, args.with_events
            ))
        
        runner.print_results(results, baseline)
        
        # Print insights
        print("\nKEY INSIGHTS (Low Contention):")
        max_overhead = max(r['per_op_us'] - baseline['per_op_us'] for r in results[1:])
        print(f"- Baseline overhead: {baseline['per_op_us']:.2f} µs/op")
        print(f"- Maximum pattern overhead: {max_overhead:.2f} µs/op")
        print(f"- All patterns suitable for production if <50 µs/op overhead")
    
    # Contention tests
    if args.with_failures or args.contention_only:
        print(f"\n\n{'#'*100}")
        print("# HIGH CONTENTION - Realistic Limits (Measuring Under Load)")
        print(f"{'#'*100}")
        
        contention_runner = BenchmarkRunner(
            iterations=DEFAULT_CONTENTION_ITERATIONS,
            runs=args.runs
        )
        
        results = []
        
        if should_run('bulkhead'):
            print("\nRunning Bulkhead with contention...")
            name_suffix = " +events" if args.with_events else ""
            results.append(await contention_runner.run_benchmark(
                f"Bulkhead (max=100){name_suffix}", benchmark_bulkhead, True, args.with_events
            ))
        
        if should_run('load'):
            print("Running Load Shedder with contention...")
            name_suffix = " +events" if args.with_events else ""
            results.append(await contention_runner.run_benchmark(
                f"Load Shedder (max=100){name_suffix}", benchmark_load_shedder, True, args.with_events
            ))
        
        if should_run('backpressure'):
            print("Running Backpressure with contention...")
            name_suffix = " +events" if args.with_events else ""
            results.append(await contention_runner.run_benchmark(
                f"Backpressure (max=100){name_suffix}", benchmark_backpressure, True, args.with_events
            ))
        
        if should_run('adaptive'):
            print("Running Adaptive Concurrency with contention...")
            name_suffix = " +events" if args.with_events else ""
            results.append(await contention_runner.run_benchmark(
                f"Adaptive Concurrency (max=100){name_suffix}", benchmark_adaptive_concurrency, True, args.with_events
            ))
        
        if args.with_failures:
            if should_run('circuit_breaker'):
                print("Running Circuit Breaker with failures...")
                name_suffix = " +events" if args.with_events else ""
                results.append(await contention_runner.run_benchmark(
                    f"Circuit Breaker (10% fail){name_suffix}", benchmark_circuit_breaker, True, args.with_events
                ))
            
            if should_run('retry'):
                print("Running Retry with failures...")
                name_suffix = " +events" if args.with_events else ""
                results.append(await contention_runner.run_benchmark(
                    f"Retry (10% fail, 3 attempts){name_suffix}", benchmark_retry, True, args.with_events
                ))
            
            if should_run('fallback'):
                print("Running Fallback with failures...")
                name_suffix = " +events" if args.with_events else ""
                results.append(await contention_runner.run_benchmark(
                    f"Fallback (10% fail){name_suffix}", benchmark_fallback, True, args.with_events
                ))
            
            if should_run('timeout'):
                print("Running Timeout with slow operations...")
                name_suffix = " +events" if args.with_events else ""
                results.append(await contention_runner.run_benchmark(
                    f"Timeout (1ms ops, 10ms timeout){name_suffix}", benchmark_timeout, True, args.with_events
                ))
        
        contention_runner.print_results(results)
        
        print("\nKEY INSIGHTS (High Contention):")
        print("- Overhead increases significantly under contention/failures")
        print("- Queuing and rejection add latency but protect system resources")
        print("- This represents realistic production scenarios with load spikes")
    
    print(f"\n{'='*100}")
    print("Benchmark complete!")
    print(f"{'='*100}\n")


if __name__ == "__main__":
    asyncio.run(main())
