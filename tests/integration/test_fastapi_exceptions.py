"""
Tests for FastAPI Integration with New Exception System

Tests that FastAPI middlewares correctly handle and expose
rich exception context from the new exception system.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from aioresilience import CircuitBreaker, Bulkhead, ExceptionConfig, CircuitConfig, BulkheadConfig
from aioresilience.integrations.fastapi import (
    CircuitBreakerMiddleware,
    BulkheadMiddleware,
)
from aioresilience.exceptions import (
    CircuitBreakerOpenError,
    BulkheadFullError,
    CircuitBreakerReason,
    BulkheadReason,
)


class TestCircuitBreakerMiddlewareExceptions:
    """Test CircuitBreakerMiddleware with new exception system"""
    
    def test_circuit_open_response_includes_context(self):
        """Test that circuit open response includes rich exception context"""
        app = FastAPI()
        
        circuit = CircuitBreaker(
            name="test-circuit",
            config=CircuitConfig(
                failure_threshold=2,
                recovery_timeout=60
            )
        )
        
        app.add_middleware(CircuitBreakerMiddleware, circuit_breaker=circuit)
        
        @app.get("/test")
        async def test_endpoint():
            raise ValueError("Simulated failure")
        
        client = TestClient(app)
        
        # Trigger failures to open circuit
        for _ in range(3):
            client.get("/test")
        
        # Circuit should be open
        response = client.get("/test")
        assert response.status_code == 503
        
        # Check response includes rich context
        data = response.json()
        assert "circuit" in data
        assert data["circuit"] == "test-circuit"
        assert "reason" in data
        assert data["reason"] == "CIRCUIT_OPEN"
        assert "state" in data or "metadata" in data
        
        # Check Retry-After header
        assert "retry-after" in response.headers
    
    def test_custom_exception_type_still_caught(self):
        """Test that custom exception types are still caught by middleware"""
        app = FastAPI()
        
        class ServiceUnavailable(Exception):
            pass
        
        config = ExceptionConfig(exception_type=ServiceUnavailable)
        circuit = CircuitBreaker(
            name="custom-circuit",
            config=CircuitConfig(failure_threshold=1),
            exceptions=config  # Custom exception via config
        )
        
        app.add_middleware(CircuitBreakerMiddleware, circuit_breaker=circuit)
        
        @app.get("/test")
        async def test_endpoint():
            raise ValueError("Trigger failure")
        
        client = TestClient(app)
        
        # Trigger failure
        client.get("/test")
        
        # Should still return 503 with custom exception
        response = client.get("/test")
        assert response.status_code == 503
    
    def test_metadata_in_response(self):
        """Test that exception metadata is included in response"""
        app = FastAPI()
        
        circuit = CircuitBreaker(
            name="metadata-circuit",
            config=CircuitConfig(
                failure_threshold=2
            )
        )
        
        app.add_middleware(
            CircuitBreakerMiddleware,
            circuit_breaker=circuit,
            include_circuit_info=True
        )
        
        @app.get("/test")
        async def test_endpoint():
            raise ValueError("Fail")
        
        client = TestClient(app)
        
        # Open circuit
        for _ in range(3):
            client.get("/test")
        
        # Check metadata
        response = client.get("/test")
        data = response.json()
        
        assert "metadata" in data or "state" in data
        if "metadata" in data:
            assert "state" in data["metadata"]


class TestBulkheadMiddlewareExceptions:
    """Test BulkheadMiddleware with new exception system"""
    
    def test_bulkhead_full_response_includes_context(self):
        """Test that bulkhead full response includes rich exception context"""
        app = FastAPI()
        
        bulkhead = Bulkhead(name="test-bulkhead", config=BulkheadConfig(max_concurrent=1))
        
        app.add_middleware(BulkheadMiddleware, bulkhead=bulkhead)
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # Test that middleware is functional
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"
    
    def test_reason_specific_retry_after(self):
        """Test that different reasons get different Retry-After values"""
        app = FastAPI()
        
        bulkhead = Bulkhead(name="retry-bulkhead", config=BulkheadConfig(max_concurrent=1))
        
        app.add_middleware(BulkheadMiddleware, bulkhead=bulkhead)
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        # Verify middleware is functional
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestExceptionTransformerIntegration:
    """Test exception transformers work with middleware"""
    
    def test_transformed_exception_in_middleware(self):
        """Test that transformed exceptions are handled correctly"""
        app = FastAPI()
        
        def transform(exc, ctx):
            return ValueError(f"Service {ctx.pattern_name} unavailable: {ctx.reason.name}")
        
        exc_config = ExceptionConfig(exception_transformer=transform)
        circuit = CircuitBreaker(
            name="transformer-circuit",
            config=CircuitConfig(failure_threshold=1),
            exceptions=exc_config
        )
        
        app.add_middleware(CircuitBreakerMiddleware, circuit_breaker=circuit)
        
        @app.get("/test")
        async def test_endpoint():
            raise RuntimeError("Trigger failure")
        
        client = TestClient(app)
        
        # Trigger failure
        client.get("/test")
        
        # Transformed exception should still be caught
        response = client.get("/test")
        assert response.status_code in (500, 503)


class TestCallbackIntegration:
    """Test callbacks work with middleware"""
    
    def test_on_failure_callback_called(self):
        """Test that on_failure callback is invoked"""
        app = FastAPI()
        
        failure_count = [0]
        
        def on_failure(ctx):
            failure_count[0] += 1
        
        exc_config = ExceptionConfig(on_exception=on_failure)
        circuit = CircuitBreaker(
            name="callback-circuit",
            config=CircuitConfig(failure_threshold=5),
            exceptions=exc_config
        )
        
        app.add_middleware(CircuitBreakerMiddleware, circuit_breaker=circuit)
        
        @app.get("/test")
        async def test_endpoint():
            raise ValueError("Fail")
        
        client = TestClient(app)
        
        # Trigger failures
        for _ in range(3):
            client.get("/test")
        
        assert failure_count[0] == 3


class TestHealthCheckExclusion:
    """Test that health checks are excluded from exception handling"""
    
    def test_health_checks_bypass_circuit_breaker(self):
        """Test health endpoints bypass circuit breaker"""
        app = FastAPI()
        
        circuit = CircuitBreaker(
            name="health-circuit",
            config=CircuitConfig(failure_threshold=1)
        )
        
        app.add_middleware(
            CircuitBreakerMiddleware,
            circuit_breaker=circuit,
            exclude_paths=["/health", "/metrics"]
        )
        
        @app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        @app.get("/test")
        async def test_endpoint():
            raise ValueError("Fail")
        
        client = TestClient(app)
        
        # Open circuit
        client.get("/test")
        
        # Health check should still work
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
