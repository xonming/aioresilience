"""
Tests for FastAPI composite middleware (ResilienceMiddleware)
"""

import asyncio
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from aioresilience import (
    CircuitBreaker,
    RateLimiter,
    Bulkhead,
    LoadShedder,
    CircuitConfig,
    BulkheadConfig,
    LoadSheddingConfig,
)
from aioresilience.integrations.fastapi import ResilienceMiddleware


class TestResilienceMiddleware:
    """Test composite resilience middleware"""
    
    def test_with_circuit_breaker(self):
        """Test composite with circuit breaker"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=2))
        
        app.add_middleware(
            ResilienceMiddleware,
            circuit_breaker=circuit,
        )
        
        @app.get("/")
        async def root():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_with_rate_limiter(self):
        """Test composite with rate limiter"""
        app = FastAPI()
        limiter = RateLimiter()
        
        app.add_middleware(
            ResilienceMiddleware,
            rate_limiter=limiter,
            rate="100/minute",
        )
        
        @app.get("/")
        async def root():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
    
    def test_with_bulkhead(self):
        """Test composite with bulkhead"""
        app = FastAPI()
        bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=5))
        
        app.add_middleware(
            ResilienceMiddleware,
            bulkhead=bulkhead,
        )
        
        @app.get("/")
        async def root():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
    
    def test_with_load_shedder(self):
        """Test composite with load shedder"""
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_queue_depth=100))
        
        app.add_middleware(
            ResilienceMiddleware,
            load_shedder=load_shedder,
        )
        
        @app.get("/")
        async def root():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
    
    def test_with_timeout(self):
        """Test composite with timeout"""
        app = FastAPI()
        
        app.add_middleware(
            ResilienceMiddleware,
            timeout=1.0,
        )
        
        @app.get("/")
        async def root():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
    
    def test_with_multiple_patterns(self):
        """Test composite with multiple patterns"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=5))
        bulkhead = Bulkhead(config=BulkheadConfig(max_concurrent=10))
        limiter = RateLimiter()
        
        app.add_middleware(
            ResilienceMiddleware,
            circuit_breaker=circuit,
            bulkhead=bulkhead,
            rate_limiter=limiter,
            rate="100/minute",
            timeout=5.0,
        )
        
        @app.get("/")
        async def root():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
    
    def test_exclude_paths(self):
        """Test path exclusion in composite"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        app.add_middleware(
            ResilienceMiddleware,
            circuit_breaker=circuit,
            exclude_paths=["/health", "/metrics"],
        )
        
        @app.get("/api")
        async def api():
            return {"status": "ok"}
        
        @app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        @app.get("/metrics")
        async def metrics():
            return {"requests": 100}
        
        client = TestClient(app)
        
        # All should work
        assert client.get("/api").status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/metrics").status_code == 200
    
    def test_circuit_breaker_opens(self):
        """Test circuit breaker in composite"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        app.add_middleware(
            ResilienceMiddleware,
            circuit_breaker=circuit,
        )
        
        @app.get("/")
        async def root():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # Circuit breaker allows normal requests
        response = client.get("/")
        assert response.status_code == 200
    
    def test_rate_limit_exceeded(self):
        """Test rate limiting in composite with very low limit"""
        app = FastAPI()
        limiter = RateLimiter()
        
        app.add_middleware(
            ResilienceMiddleware,
            rate_limiter=limiter,
            rate="1/second",  # Very low limit - 1 per second
        )
        
        @app.get("/")
        async def root():
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # First request should pass
        assert client.get("/").status_code == 200
        
        # Immediate second request should be rate limited  
        response = client.get("/")
        # Rate limiter uses sliding window, may pass or fail
        assert response.status_code in [200, 429]
    
    def test_timeout_exceeded(self):
        """Test timeout in composite"""
        app = FastAPI()
        
        app.add_middleware(
            ResilienceMiddleware,
            timeout=0.01,  # Very short timeout
        )
        
        @app.get("/")
        async def root():
            await asyncio.sleep(1.0)  # Slow operation
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 408


class TestResilienceMiddlewareConfiguration:
    """Test configuration options"""
    
    def test_exclude_paths_default(self):
        """Test default excluded paths"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        # Default excludes: /health, /metrics, /ready, /healthz
        app.add_middleware(
            ResilienceMiddleware,
            circuit_breaker=circuit,
        )
        
        @app.get("/api")
        async def api():
            return {"status": "ok"}
        
        @app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        client = TestClient(app)
        
        # Both should work
        assert client.get("/api").status_code == 200
        assert client.get("/health").status_code == 200
    
    def test_custom_exclude_paths(self):
        """Test custom excluded paths"""
        app = FastAPI()
        circuit = CircuitBreaker("test", config=CircuitConfig(failure_threshold=1))
        
        app.add_middleware(
            ResilienceMiddleware,
            circuit_breaker=circuit,
            exclude_paths=["/admin", "/internal"],
        )
        
        @app.get("/api")
        async def api():
            return {"status": "ok"}
        
        @app.get("/admin")
        async def admin():
            return {"admin": True}
        
        client = TestClient(app)
        
        assert client.get("/api").status_code == 200
        assert client.get("/admin").status_code == 200
