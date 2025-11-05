"""
Tests for aiohttp Integration
"""

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aioresilience import CircuitBreaker, RateLimiter, Bulkhead, LoadShedder
from aioresilience.integrations.aiohttp import (
    circuit_breaker_handler,
    rate_limit_handler,
    timeout_handler,
    bulkhead_handler,
    with_fallback_handler,
    create_resilience_middleware,
    get_client_ip,
)


class TestAiohttpDecorators:
    """Test aiohttp handler decorators"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_handler_success(self):
        """Test circuit breaker decorator allows successful requests"""
        circuit = CircuitBreaker(name="test", failure_threshold=3)
        
        @circuit_breaker_handler(circuit)
        async def test_handler(request):
            return web.json_response({"status": "ok"})
        
        app = web.Application()
        app.router.add_get("/test", test_handler)
        
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_bulkhead_handler_success(self):
        """Test bulkhead decorator allows requests within limit"""
        bulkhead = Bulkhead(max_concurrent=10)
        
        @bulkhead_handler(bulkhead)
        async def test_handler(request):
            return web.json_response({"status": "ok"})
        
        app = web.Application()
        app.router.add_get("/test", test_handler)
        
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_timeout_handler_success(self):
        """Test timeout decorator allows fast requests"""
        @timeout_handler(5.0)
        async def test_handler(request):
            return web.json_response({"status": "ok"})
        
        app = web.Application()
        app.router.add_get("/test", test_handler)
        
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_timeout_handler_exceeds(self):
        """Test timeout decorator rejects slow requests"""
        import asyncio
        
        @timeout_handler(0.1)
        async def test_handler(request):
            await asyncio.sleep(1.0)
            return web.json_response({"status": "ok"})
        
        app = web.Application()
        app.router.add_get("/test", test_handler)
        
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 408
            data = await resp.json()
            assert "timeout" in data["error"].lower()
    
    @pytest.mark.asyncio
    async def test_with_fallback_handler_on_error(self):
        """Test fallback decorator returns fallback on error"""
        @with_fallback_handler({"status": "fallback"})
        async def test_handler(request):
            raise Exception("Test error")
        
        app = web.Application()
        app.router.add_get("/test", test_handler)
        
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "fallback"
    
    @pytest.mark.asyncio
    async def test_with_fallback_handler_success(self):
        """Test fallback decorator doesn't interfere with success"""
        @with_fallback_handler({"status": "fallback"})
        async def test_handler(request):
            return web.json_response({"status": "success"})
        
        app = web.Application()
        app.router.add_get("/test", test_handler)
        
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "success"


class TestAiohttpMiddleware:
    """Test create_resilience_middleware function"""
    
    @pytest.mark.asyncio
    async def test_create_resilience_middleware_basic(self):
        """Test basic resilience middleware"""
        load_shedder = LoadShedder(max_requests=100)
        
        app = web.Application()
        app.middlewares.append(create_resilience_middleware(
            load_shedder=load_shedder
        ))
        
        async def test_handler(request):
            return web.json_response({"status": "ok"})
        
        app.router.add_get("/test", test_handler)
        
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 200
    
    @pytest.mark.asyncio
    async def test_middleware_excludes_health_endpoints(self):
        """Test that health endpoints are excluded from resilience"""
        load_shedder = LoadShedder(max_requests=0)  # Reject all
        
        app = web.Application()
        app.middlewares.append(create_resilience_middleware(
            load_shedder=load_shedder
        ))
        
        async def health_handler(request):
            return web.json_response({"status": "healthy"})
        
        app.router.add_get("/health", health_handler)
        
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            # Health endpoint should not be affected by load shedding
            resp = await client.get("/health")
            assert resp.status == 200
    
    @pytest.mark.asyncio
    async def test_middleware_with_timeout(self):
        """Test middleware with timeout"""
        import asyncio
        
        app = web.Application()
        app.middlewares.append(create_resilience_middleware(
            timeout=0.1
        ))
        
        async def slow_handler(request):
            await asyncio.sleep(1.0)
            return web.json_response({"status": "ok"})
        
        app.router.add_get("/test", slow_handler)
        
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 408


class TestAiohttpUtils:
    """Test aiohttp utility functions"""
    
    def test_get_client_ip_direct(self):
        """Test get_client_ip with direct connection"""
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.headers = {}
        mock_transport = Mock()
        mock_transport.get_extra_info.return_value = ("127.0.0.1", 12345)
        mock_request.transport = mock_transport
        
        ip = get_client_ip(mock_request)
        assert ip == "127.0.0.1"
    
    def test_get_client_ip_with_forwarded_for(self):
        """Test get_client_ip with X-Forwarded-For header"""
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.headers = {
            "X-Forwarded-For": "192.168.1.100, 10.0.0.1"
        }
        
        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.100"
    
    def test_get_client_ip_with_real_ip(self):
        """Test get_client_ip with X-Real-IP header"""
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.headers = {
            "X-Real-IP": "192.168.1.200"
        }
        
        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.200"
    
    def test_get_client_ip_priority(self):
        """Test that X-Forwarded-For has priority"""
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.headers = {
            "X-Forwarded-For": "192.168.1.100",
            "X-Real-IP": "192.168.1.200"
        }
        
        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.100"


class TestAiohttpIntegration:
    """Integration tests combining multiple patterns"""
    
    @pytest.mark.asyncio
    async def test_multiple_decorators(self):
        """Test stacking multiple decorators"""
        circuit = CircuitBreaker(name="test")
        bulkhead = Bulkhead(max_concurrent=10)
        
        @circuit_breaker_handler(circuit)
        @bulkhead_handler(bulkhead)
        @timeout_handler(5.0)
        @with_fallback_handler({"status": "fallback"})
        async def test_handler(request):
            return web.json_response({"status": "success"})
        
        app = web.Application()
        app.router.add_get("/test", test_handler)
        
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_decorator_with_fallback_on_error(self):
        """Test decorators with fallback when error occurs"""
        circuit = CircuitBreaker(name="test")
        
        @circuit_breaker_handler(circuit)
        @with_fallback_handler({"status": "fallback"})
        async def test_handler(request):
            raise ValueError("Test error")
        
        app = web.Application()
        app.router.add_get("/test", test_handler)
        
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            # Fallback should catch the error
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "fallback"
    
    @pytest.mark.asyncio
    async def test_middleware_and_decorators_combined(self):
        """Test middleware and decorators working together"""
        load_shedder = LoadShedder(max_requests=100)
        bulkhead = Bulkhead(max_concurrent=10)
        
        app = web.Application()
        app.middlewares.append(create_resilience_middleware(
            load_shedder=load_shedder
        ))
        
        @bulkhead_handler(bulkhead)
        async def test_handler(request):
            return web.json_response({"status": "success"})
        
        app.router.add_get("/test", test_handler)
        
        from aiohttp.test_utils import TestClient, TestServer
        async with TestClient(TestServer(app)) as client:
            resp = await client.get("/test")
            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "success"
