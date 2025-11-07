"""
Comprehensive tests for FastAPI Circuit Breaker Middleware
"""

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.responses import JSONResponse

from aioresilience import CircuitBreaker, CircuitConfig
from aioresilience.integrations.fastapi import CircuitBreakerMiddleware


class TestCircuitBreakerMiddlewareAdvanced:
    """Test advanced circuit breaker middleware features"""
    
    def test_custom_response_factory(self):
        """Test circuit breaker with custom response factory"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        # Custom response factory
        def custom_response(cb, request):
            return JSONResponse(
                status_code=503,
                content={"custom": "response", "path": str(request.url.path)},
                headers={"X-Custom": "Header"}
            )
        
        app.add_middleware(
            CircuitBreakerMiddleware,
            circuit_breaker=circuit,
            response_factory=custom_response
        )
        
        @app.get("/test")
        async def test_endpoint():
            raise Exception("Fail")
        
        client = TestClient(app, raise_server_exceptions=False)
        
        # First request opens circuit
        client.get("/test")
        
        # Second request should use custom response
        response = client.get("/test")
        assert response.status_code == 503
        data = response.json()
        assert data["custom"] == "response"
        assert data["path"] == "/test"
        assert response.headers["x-custom"] == "Header"
    
    def test_custom_error_detail_factory(self):
        """Test circuit breaker with custom error detail factory"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        # Custom error detail factory
        def custom_details(cb):
            return {
                "error_type": "circuit_open",
                "circuit_name": cb.name,
                "custom_field": "custom_value"
            }
        
        app.add_middleware(
            CircuitBreakerMiddleware,
            circuit_breaker=circuit,
            error_detail_factory=custom_details
        )
        
        @app.get("/test")
        async def test_endpoint():
            raise Exception("Fail")
        
        client = TestClient(app, raise_server_exceptions=False)
        
        # First request opens circuit
        client.get("/test")
        
        # Second request should use custom details
        response = client.get("/test")
        assert response.status_code == 503
        data = response.json()
        assert data["error_type"] == "circuit_open"
        assert data["circuit_name"] == "test"
        assert data["custom_field"] == "custom_value"
    
    def test_circuit_breaker_with_5xx_response(self):
        """Test that 5xx responses trigger circuit breaker failures"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        app.add_middleware(CircuitBreakerMiddleware, circuit_breaker=circuit)
        
        call_count = [0]
        
        @app.get("/test")
        async def test_endpoint():
            call_count[0] += 1
            return JSONResponse(status_code=500, content={"error": "server error"})
        
        client = TestClient(app, raise_server_exceptions=False)
        
        # First 500 response should open circuit
        response1 = client.get("/test")
        # Our middleware converts 5xx to exception, which triggers circuit breaker
        # The circuit then returns 503
        assert response1.status_code in [500, 503]
        
        # Subsequent request should be blocked by open circuit
        response2 = client.get("/test")
        assert response2.status_code == 503
        
        # Verify circuit breaker is actually blocking
        data = response2.json()
        assert "circuit" in data or "detail" in data
    
    def test_exclude_paths_functionality(self):
        """Test that excluded paths bypass circuit breaker"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        app.add_middleware(
            CircuitBreakerMiddleware,
            circuit_breaker=circuit,
            exclude_paths=["/health", "/status"]
        )
        
        @app.get("/health")
        async def health():
            return {"status": "ok"}
        
        @app.get("/status")
        async def status():
            return {"status": "up"}
        
        @app.get("/api/test")
        async def api_test():
            raise Exception("Fail")
        
        client = TestClient(app, raise_server_exceptions=False)
        
        # Open the circuit
        client.get("/api/test")
        client.get("/api/test")
        
        # Excluded paths should still work
        response = client.get("/health")
        assert response.status_code == 200
        
        response = client.get("/status")
        assert response.status_code == 200
        
        # Regular API path should be blocked
        response = client.get("/api/test")
        assert response.status_code == 503
    
    def test_custom_status_code_and_message(self):
        """Test circuit breaker with custom status code and error message"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        app.add_middleware(
            CircuitBreakerMiddleware,
            circuit_breaker=circuit,
            error_message="Custom service unavailable message",
            status_code=429  # Custom status code
        )
        
        @app.get("/test")
        async def test_endpoint():
            raise Exception("Fail")
        
        client = TestClient(app, raise_server_exceptions=False)
        
        # Open circuit
        client.get("/test")
        
        # Check custom response
        response = client.get("/test")
        assert response.status_code == 429
        data = response.json()
        assert data["detail"] == "Custom service unavailable message"
    
    def test_custom_retry_after_header(self):
        """Test circuit breaker with custom retry-after value"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(
            failure_threshold=1,
            recovery_timeout=120.0
        ))
        
        app.add_middleware(
            CircuitBreakerMiddleware,
            circuit_breaker=circuit,
            retry_after=30  # Custom retry-after
        )
        
        @app.get("/test")
        async def test_endpoint():
            raise Exception("Fail")
        
        client = TestClient(app, raise_server_exceptions=False)
        
        # Open circuit
        client.get("/test")
        
        # Check retry-after header
        response = client.get("/test")
        assert response.status_code == 503
        assert response.headers["retry-after"] == "30"
    
    def test_include_circuit_info_disabled(self):
        """Test circuit breaker with circuit info disabled"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        app.add_middleware(
            CircuitBreakerMiddleware,
            circuit_breaker=circuit,
            include_circuit_info=False
        )
        
        @app.get("/test")
        async def test_endpoint():
            raise Exception("Fail")
        
        client = TestClient(app, raise_server_exceptions=False)
        
        # Open circuit
        client.get("/test")
        
        # Check response doesn't include circuit info
        response = client.get("/test")
        assert response.status_code == 503
        data = response.json()
        assert "circuit" not in data
        assert "state" not in data
    
    def test_circuit_breaker_with_successful_requests(self):
        """Test that successful requests don't trigger circuit breaker"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=3))
        
        app.add_middleware(CircuitBreakerMiddleware, circuit_breaker=circuit)
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # Multiple successful requests
        for _ in range(5):
            response = client.get("/test")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
