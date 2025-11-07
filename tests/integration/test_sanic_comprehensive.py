"""
Comprehensive tests for Sanic integrations to boost coverage
Uses async ASGI client pattern that works correctly
"""

import asyncio
import uuid
import pytest
from sanic import Sanic, response
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
from aioresilience.integrations.sanic import (
    circuit_breaker_route,
    rate_limit_route,
    timeout_route,
    bulkhead_route,
    with_fallback_route,
    backpressure_route,
    adaptive_concurrency_route,
)


class TestSanicCircuitBreakerComprehensive:
    """Comprehensive circuit breaker tests"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_on_failure(self):
        """Test circuit opens after failure threshold"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        @app.get("/test")
        @circuit_breaker_route(circuit)
        async def handler(request):
            raise Exception("Fail")
        
        # First request fails and opens circuit
        _, resp1 = await app.asgi_client.get("/test")
        assert resp1.status == 503
        
        # Second request blocked by open circuit
        _, resp2 = await app.asgi_client.get("/test")
        assert resp2.status == 503
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_custom_params(self):
        """Test circuit breaker with all custom parameters"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        @app.get("/test")
        @circuit_breaker_route(
            circuit,
            error_message="Custom error",
            status_code=500,
            retry_after=60,
            include_info=False
        )
        async def handler(request):
            raise Exception("Fail")
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 500
        # Response contains error info (may be wrapped by Sanic)
        assert "error" in resp.json


class TestSanicRateLimitComprehensive:
    """Comprehensive rate limit tests"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_with_custom_key_function(self):
        """Test rate limiting with custom key extractor"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        limiter = RateLimiter()
        
        def custom_key(request):
            return request.headers.get("X-User-ID", "anonymous")
        
        @app.get("/test")
        @rate_limit_route(limiter, "100/minute", key_func=custom_key)
        async def handler(request):
            return response.json({"status": "ok"})
        
        _, resp = await app.asgi_client.get("/test", headers={"X-User-ID": "user123"})
        assert resp.status == 200
    
    @pytest.mark.asyncio
    async def test_rate_limit_with_all_custom_params(self):
        """Test rate limiting with all parameters"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        limiter = RateLimiter()
        
        @app.get("/test")
        @rate_limit_route(
            limiter,
            "100/minute",
            error_message="Too many requests",
            status_code=429,
            retry_after=120
        )
        async def handler(request):
            return response.json({"status": "ok"})
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200


class TestSanicTimeoutComprehensive:
    """Comprehensive timeout tests"""
    
    @pytest.mark.asyncio
    async def test_timeout_exceeded(self):
        """Test timeout is enforced"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        
        @app.get("/test")
        @timeout_route(0.01)
        async def handler(request):
            await asyncio.sleep(1.0)
            return response.json({"status": "ok"})
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 408
    
    @pytest.mark.asyncio
    async def test_timeout_with_custom_params(self):
        """Test timeout with custom parameters"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        
        @app.get("/test")
        @timeout_route(
            0.01,
            error_message="Request timeout",
            status_code=408
        )
        async def handler(request):
            await asyncio.sleep(1.0)
            return response.json({"status": "ok"})
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 408
        assert "timeout" in str(resp.json).lower()


class TestSanicBulkheadComprehensive:
    """Comprehensive bulkhead tests"""
    
    @pytest.mark.asyncio
    async def test_bulkhead_executes_successfully(self):
        """Test bulkhead allows execution"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=10))
        
        @app.get("/test")
        @bulkhead_route(bulkhead)
        async def handler(request):
            return response.json({"status": "ok"})
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200
    
    @pytest.mark.asyncio
    async def test_bulkhead_with_custom_params(self):
        """Test bulkhead with custom error parameters"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=10))
        
        @app.get("/test")
        @bulkhead_route(
            bulkhead,
            error_message="Service at capacity",
            status_code=503
        )
        async def handler(request):
            return response.json({"status": "ok"})
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200


class TestSanicFallbackComprehensive:
    """Comprehensive fallback tests"""
    
    @pytest.mark.asyncio
    async def test_fallback_on_exception(self):
        """Test fallback returns fallback value on exception"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        
        @app.get("/test")
        @with_fallback_route({"status": "fallback", "data": []})
        async def handler(request):
            raise ValueError("Something went wrong")
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200
        assert resp.json["status"] == "fallback"
    
    @pytest.mark.asyncio
    async def test_fallback_success_path(self):
        """Test fallback doesn't interfere with success"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        
        @app.get("/test")
        @with_fallback_route({"status": "fallback"})
        async def handler(request):
            return response.json({"status": "success"})
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200
        assert resp.json["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_fallback_with_different_exception_types(self):
        """Test fallback handles different exception types"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        
        @app.get("/test")
        @with_fallback_route({"error": True})
        async def handler(request):
            raise RuntimeError("Runtime error")
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200
        assert resp.json["error"] is True


class TestSanicBackpressureComprehensive:
    """Comprehensive backpressure tests"""
    
    @pytest.mark.asyncio
    async def test_backpressure_allows_within_capacity(self):
        """Test backpressure allows requests within capacity"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        bp = BackpressureManager(config=BackpressureConfig(max_pending=10, high_water_mark=8, low_water_mark=3))
        
        @app.get("/test")
        @backpressure_route(bp)
        async def handler(request):
            return response.json({"status": "ok"})
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200
    
    @pytest.mark.asyncio
    async def test_backpressure_with_custom_timeout(self):
        """Test backpressure with custom timeout"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        bp = BackpressureManager(config=BackpressureConfig(max_pending=10, high_water_mark=8, low_water_mark=3))
        
        @app.get("/test")
        @backpressure_route(bp, timeout=2.0)
        async def handler(request):
            return response.json({"status": "ok"})
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200
    
    @pytest.mark.asyncio
    async def test_backpressure_with_custom_error(self):
        """Test backpressure with custom error params"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        bp = BackpressureManager(config=BackpressureConfig(max_pending=10, high_water_mark=8, low_water_mark=3))
        
        @app.get("/test")
        @backpressure_route(
            bp,
            timeout=2.0,
            error_message="System overloaded",
            status_code=503
        )
        async def handler(request):
            return response.json({"status": "ok"})
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200


class TestSanicAdaptiveConcurrencyComprehensive:
    """Comprehensive adaptive concurrency tests"""
    
    @pytest.mark.asyncio
    async def test_adaptive_concurrency_allows_requests(self):
        """Test adaptive concurrency allows requests"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        config = AdaptiveConcurrencyConfig(initial_limit=10)
        limiter = AdaptiveConcurrencyLimiter("test", config)
        
        @app.get("/test")
        @adaptive_concurrency_route(limiter)
        async def handler(request):
            return response.json({"status": "ok"})
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200
    
    @pytest.mark.asyncio
    async def test_adaptive_concurrency_with_custom_error(self):
        """Test adaptive concurrency with custom error params"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        config = AdaptiveConcurrencyConfig(initial_limit=10)
        limiter = AdaptiveConcurrencyLimiter("test", config)
        
        @app.get("/test")
        @adaptive_concurrency_route(
            limiter,
            error_message="Concurrency limit exceeded",
            status_code=503
        )
        async def handler(request):
            return response.json({"status": "ok"})
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200


class TestSanicDecoratorCombinations:
    """Test combining multiple decorators"""
    
    @pytest.mark.asyncio
    async def test_stacking_all_decorators(self):
        """Test all decorators work when stacked"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=5))
        bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=10))
        limiter = RateLimiter()
        bp = BackpressureManager(config=BackpressureConfig(max_pending=10, high_water_mark=8, low_water_mark=3))
        ac_config = AdaptiveConcurrencyConfig(initial_limit=10)
        ac = AdaptiveConcurrencyLimiter("test", ac_config)
        
        @app.get("/test")
        @circuit_breaker_route(circuit)
        @bulkhead_route(bulkhead)
        @rate_limit_route(limiter, "100/minute")
        @timeout_route(5.0)
        @backpressure_route(bp)
        @adaptive_concurrency_route(ac)
        @with_fallback_route({"status": "fallback"})
        async def handler(request):
            return response.json({"status": "success"})
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200
        assert resp.json["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_error_handling_through_decorator_chain(self):
        """Test error propagates correctly through decorators"""
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=10))
        
        @app.get("/test")
        @circuit_breaker_route(circuit)
        @timeout_route(5.0)
        @with_fallback_route({"error": True, "fallback": True})
        async def handler(request):
            raise Exception("Test error")
        
        _, resp = await app.asgi_client.get("/test")
        assert resp.status == 200
        assert resp.json.get("fallback") is True
