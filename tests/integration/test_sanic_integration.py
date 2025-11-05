"""
Tests for Sanic Integration
"""

import pytest
from sanic import Sanic, response as sanic_response
from aioresilience import CircuitBreaker, RateLimiter, Bulkhead
from aioresilience.integrations.sanic import (
    circuit_breaker_route,
    rate_limit_route,
    timeout_route,
    bulkhead_route,
    with_fallback_route,
    setup_resilience,
    get_client_ip,
)


class TestSanicDecorators:
    """Test Sanic route decorators"""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_route_success(self):
        """Test circuit breaker decorator allows successful requests"""
        import uuid
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        circuit = CircuitBreaker(name="test", failure_threshold=3)
        
        @app.get("/test")
        @circuit_breaker_route(circuit)
        async def test_route(request):
            return sanic_response.json({"status": "ok"})
        
        _, response = await app.asgi_client.get("/test")
        assert response.status == 200
        assert response.json["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_bulkhead_route_success(self):
        """Test bulkhead decorator allows requests within limit"""
        import uuid
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        bulkhead = Bulkhead(max_concurrent=10)
        
        @app.get("/test")
        @bulkhead_route(bulkhead)
        async def test_route(request):
            return sanic_response.json({"status": "ok"})
        
        _, response = await app.asgi_client.get("/test")
        assert response.status == 200
        assert response.json["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_timeout_route_success(self):
        """Test timeout decorator allows fast requests"""
        import uuid
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        
        @app.get("/test")
        @timeout_route(5.0)
        async def test_route(request):
            return sanic_response.json({"status": "ok"})
        
        _, response = await app.asgi_client.get("/test")
        assert response.status == 200
        assert response.json["status"] == "ok"
    
    @pytest.mark.asyncio
    async def test_timeout_route_exceeds(self):
        """Test timeout decorator rejects slow requests"""
        import asyncio
        
        import uuid
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        
        @app.get("/test")
        @timeout_route(0.1)
        async def test_route(request):
            await asyncio.sleep(1.0)
            return sanic_response.json({"status": "ok"})
        
        _, response = await app.asgi_client.get("/test")
        assert response.status == 408
        assert "timeout" in response.json["error"].lower()
    
    @pytest.mark.asyncio
    async def test_with_fallback_route_on_error(self):
        """Test fallback decorator returns fallback on error"""
        import uuid
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        
        @app.get("/test")
        @with_fallback_route({"status": "fallback"})
        async def test_route(request):
            raise Exception("Test error")
        
        _, response = await app.asgi_client.get("/test")
        assert response.status == 200
        assert response.json["status"] == "fallback"
    
    @pytest.mark.asyncio
    async def test_with_fallback_route_success(self):
        """Test fallback decorator doesn't interfere with success"""
        import uuid
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        
        @app.get("/test")
        @with_fallback_route({"status": "fallback"})
        async def test_route(request):
            return sanic_response.json({"status": "success"})
        
        _, response = await app.asgi_client.get("/test")
        assert response.status == 200
        assert response.json["status"] == "success"


class TestSanicSetupResilience:
    """Test setup_resilience function"""
    
    @pytest.mark.asyncio
    async def test_setup_resilience_basic(self):
        """Test basic resilience setup"""
        from aioresilience import LoadShedder
        
        import uuid
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        load_shedder = LoadShedder(max_requests=100)
        
        setup_resilience(app, load_shedder=load_shedder)
        
        @app.get("/test")
        async def test_route(request):
            return sanic_response.json({"status": "ok"})
        
        _, response = await app.asgi_client.get("/test")
        assert response.status == 200
    
    @pytest.mark.asyncio
    async def test_setup_resilience_excludes_health_endpoints(self):
        """Test that health endpoints are excluded from resilience"""
        from aioresilience import LoadShedder
        
        import uuid
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        load_shedder = LoadShedder(max_requests=0)  # Reject all
        
        setup_resilience(app, load_shedder=load_shedder)
        
        @app.get("/health")
        async def health(request):
            return sanic_response.json({"status": "healthy"})
        
        # Health endpoint should not be affected by load shedding
        _, response = await app.asgi_client.get("/health")
        assert response.status == 200


class TestSanicUtils:
    """Test Sanic utility functions"""
    
    def test_get_client_ip_direct(self):
        """Test get_client_ip with direct connection"""
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.ip = "127.0.0.1"
        mock_request.headers = {}
        
        ip = get_client_ip(mock_request)
        assert ip == "127.0.0.1"
    
    def test_get_client_ip_with_forwarded_for(self):
        """Test get_client_ip with X-Forwarded-For header"""
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.ip = "127.0.0.1"
        mock_request.headers = {
            "X-Forwarded-For": "192.168.1.100, 10.0.0.1"
        }
        
        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.100"
    
    def test_get_client_ip_with_real_ip(self):
        """Test get_client_ip with X-Real-IP header"""
        from unittest.mock import Mock
        
        mock_request = Mock()
        mock_request.ip = "127.0.0.1"
        mock_request.headers = {
            "X-Real-IP": "192.168.1.200"
        }
        
        ip = get_client_ip(mock_request)
        assert ip == "192.168.1.200"


class TestSanicIntegration:
    """Integration tests combining multiple patterns"""
    
    @pytest.mark.asyncio
    async def test_multiple_decorators(self):
        """Test stacking multiple decorators"""
        import uuid
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        circuit = CircuitBreaker(name="test")
        bulkhead = Bulkhead(max_concurrent=10)
        
        @app.get("/test")
        @circuit_breaker_route(circuit)
        @bulkhead_route(bulkhead)
        @timeout_route(5.0)
        @with_fallback_route({"status": "fallback"})
        async def test_route(request):
            return sanic_response.json({"status": "success"})
        
        _, response = await app.asgi_client.get("/test")
        assert response.status == 200
        assert response.json["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_decorator_with_fallback_on_error(self):
        """Test decorators with fallback when error occurs"""
        import uuid
        app = Sanic(f"test_app_{uuid.uuid4().hex[:8]}")
        circuit = CircuitBreaker(name="test")
        
        @app.get("/test")
        @circuit_breaker_route(circuit)
        @with_fallback_route({"status": "fallback"})
        async def test_route(request):
            raise ValueError("Test error")
        
        _, response = await app.asgi_client.get("/test")
        # Fallback should catch the error
        assert response.status == 200
        assert response.json["status"] == "fallback"
