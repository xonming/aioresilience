"""
Additional aiohttp integration tests for coverage
"""

import asyncio
import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from aioresilience import (
    CircuitBreaker,
    RateLimiter,
    Bulkhead,
    BackpressureManager,
    AdaptiveConcurrencyLimiter,
    CircuitConfig,
    BulkheadConfig,
    BackpressureConfig,
)
from aioresilience.config import AdaptiveConcurrencyConfig
from aioresilience.integrations.aiohttp import (
    circuit_breaker_handler,
    rate_limit_handler,
    timeout_handler,
    bulkhead_handler,
    with_fallback_handler,
    backpressure_handler,
    adaptive_concurrency_handler,
)


class TestAiohttpCircuitBreakerExtended:
    """Extended circuit breaker tests"""
    
    @pytest.mark.asyncio
    async def test_circuit_with_custom_status_code(self):
        """Test circuit breaker with custom status code"""
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        @circuit_breaker_handler(circuit, status_code=500)
        async def handler(request):
            raise Exception("Fail")
        
        app = web.Application()
        app.router.add_get("/test", handler)
        
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 500


class TestAiohttpRateLimitExtended:
    """Extended rate limit tests"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_with_key_func(self):
        """Test rate limiting with custom key function"""
        limiter = RateLimiter()
        
        def custom_key(request):
            return request.headers.get("X-API-Key", "default")
        
        @rate_limit_handler(limiter, "100/minute", key_func=custom_key)
        async def handler(request):
            return web.json_response({"status": "ok"})
        
        app = web.Application()
        app.router.add_get("/test", handler)
        
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test", headers={"X-API-Key": "key1"})
            assert resp.status == 200
    
    @pytest.mark.asyncio
    async def test_rate_limit_custom_error(self):
        """Test custom error message and status"""
        limiter = RateLimiter()
        
        @rate_limit_handler(
            limiter,
            "100/minute",
            error_message="Custom rate limit error",
            status_code=429
        )
        async def handler(request):
            return web.json_response({"status": "ok"})
        
        app = web.Application()
        app.router.add_get("/test", handler)
        
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 200


class TestAiohttpBackpressureExtended:
    """Extended backpressure tests"""
    
    @pytest.mark.asyncio
    async def test_backpressure_with_custom_timeout(self):
        """Test backpressure with custom timeout"""
        backpressure = BackpressureManager(config=BackpressureConfig(max_pending=10, high_water_mark=8, low_water_mark=3))
        
        @backpressure_handler(backpressure, timeout=1.0)
        async def handler(request):
            return web.json_response({"status": "ok"})
        
        app = web.Application()
        app.router.add_get("/test", handler)
        
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 200


class TestAiohttpAdaptiveConcurrencyExtended:
    """Extended adaptive concurrency tests"""
    
    @pytest.mark.asyncio
    async def test_adaptive_concurrency_basic(self):
        """Test adaptive concurrency allows requests"""
        config = AdaptiveConcurrencyConfig(initial_limit=10)
        limiter = AdaptiveConcurrencyLimiter("test", config)
        
        @adaptive_concurrency_handler(limiter)
        async def handler(request):
            return web.json_response({"status": "ok"})
        
        app = web.Application()
        app.router.add_get("/test", handler)
        
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 200


class TestAiohttpBulkheadExtended:
    """Extended bulkhead tests"""
    
    @pytest.mark.asyncio
    async def test_bulkhead_with_custom_error(self):
        """Test bulkhead with custom error message"""
        bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=5))
        
        @bulkhead_handler(bulkhead, error_message="Custom capacity error")
        async def handler(request):
            return web.json_response({"status": "ok"})
        
        app = web.Application()
        app.router.add_get("/test", handler)
        
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 200
