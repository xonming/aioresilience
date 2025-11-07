"""
Tests for FastAPI Integration
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock
from aioresilience import LoadShedder, RateLimiter, LoadSheddingConfig

# Skip all tests if FastAPI is not installed
fastapi = pytest.importorskip("fastapi", reason="FastAPI not installed")
starlette = pytest.importorskip("starlette", reason="Starlette not installed")

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse
from aioresilience.integrations.fastapi import (
    LoadSheddingMiddleware,
    get_client_ip,
    rate_limit_dependency,
)


class TestLoadSheddingMiddleware:
    """Test LoadSheddingMiddleware"""

    def test_middleware_allows_requests_under_limit(self):
        """Test middleware allows requests when under limit"""
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=10))
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        with TestClient(app) as client:
            response = client.get("/test")
            
            assert response.status_code == 200
            assert response.json() == {"status": "ok"}

    def test_middleware_sheds_load_when_overloaded(self):
        """Test middleware sheds load when overloaded"""
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=1))
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
        
        @app.get("/slow")
        async def slow_endpoint():
            await asyncio.sleep(0.1)
            return {"status": "ok"}
        
        with TestClient(app) as client:
            # First request should succeed (but we'll test without async)
            # For testing, we'll fill the load shedder manually
            import asyncio
            asyncio.run(load_shedder.acquire())
            
            # Second request should be shed
            response = client.get("/slow")
            
            assert response.status_code == 503
            assert "overloaded" in response.json()["detail"].lower()
            assert "Retry-After" in response.headers

    def test_middleware_skips_health_endpoints(self):
        """Test middleware skips health check endpoints"""
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=1))  # Very low capacity
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
        
        @app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        @app.get("/healthz")
        async def healthz():
            return {"status": "healthy"}
        
        @app.get("/ready")
        async def ready():
            return {"status": "ready"}
        
        @app.get("/metrics")
        async def metrics():
            return {"requests": 100}
        
        with TestClient(app) as client:
            # All health endpoints should bypass load shedding
            assert client.get("/health").status_code == 200
            assert client.get("/healthz").status_code == 200
            assert client.get("/ready").status_code == 200
            assert client.get("/metrics").status_code == 200

    def test_middleware_respects_priority_header(self):
        """Test middleware respects X-Priority header"""
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=10))
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        with TestClient(app) as client:
            # Request with high priority header
            response = client.get("/test", headers={"X-Priority": "high"})
            assert response.status_code == 200

    def test_middleware_releases_on_success(self):
        """Test middleware releases slot after successful request"""
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=10))
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
        
        @app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}
        
        with TestClient(app) as client:
            assert load_shedder.active_requests == 0
            response = client.get("/test")
            assert response.status_code == 200
            assert load_shedder.active_requests == 0  # Should be released

    def test_middleware_releases_on_error(self):
        """Test middleware releases slot even on error"""
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=10))
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
        
        @app.get("/error")
        async def error_endpoint():
            raise ValueError("Test error")
        
        with TestClient(app) as client:
            assert load_shedder.active_requests == 0
            
            # Request should raise error but still release
            with pytest.raises(ValueError):
                client.get("/error")
            
            assert load_shedder.active_requests == 0


class TestGetClientIP:
    """Test get_client_ip function"""

    @pytest.mark.asyncio
    async def test_get_client_ip_direct(self):
        """Test getting client IP from direct connection"""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "192.168.1.100"
        
        ip = get_client_ip(request)
        assert ip == "192.168.1.100"

    @pytest.mark.asyncio
    async def test_get_client_ip_from_x_forwarded_for(self):
        """Test getting client IP from X-Forwarded-For header"""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "10.0.0.1, 10.0.0.2, 10.0.0.3"}
        request.client = Mock()
        request.client.host = "192.168.1.100"
        
        ip = get_client_ip(request)
        assert ip == "10.0.0.1"  # Should get first IP in chain

    @pytest.mark.asyncio
    async def test_get_client_ip_from_x_real_ip(self):
        """Test getting client IP from X-Real-IP header"""
        request = Mock(spec=Request)
        request.headers = {"X-Real-IP": "10.0.0.50"}
        request.client = Mock()
        request.client.host = "192.168.1.100"
        
        ip = get_client_ip(request)
        assert ip == "10.0.0.50"

    @pytest.mark.asyncio
    async def test_get_client_ip_prefers_x_forwarded_for(self):
        """Test X-Forwarded-For takes precedence over X-Real-IP"""
        request = Mock(spec=Request)
        request.headers = {
            "X-Forwarded-For": "10.0.0.1",
            "X-Real-IP": "10.0.0.2"
        }
        request.client = Mock()
        request.client.host = "192.168.1.100"
        
        ip = get_client_ip(request)
        assert ip == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_get_client_ip_strips_whitespace(self):
        """Test that IP addresses are stripped of whitespace"""
        request = Mock(spec=Request)
        request.headers = {"X-Forwarded-For": "  10.0.0.1  , 10.0.0.2"}
        
        ip = get_client_ip(request)
        assert ip == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_get_client_ip_no_client(self):
        """Test fallback when request.client is None"""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = None
        
        ip = get_client_ip(request)
        assert ip == "unknown"

    @pytest.mark.asyncio
    async def test_get_client_ip_empty_headers(self):
        """Test with empty forwarded headers"""
        request = Mock(spec=Request)
        request.headers = {}
        request.client = Mock()
        request.client.host = "127.0.0.1"
        
        ip = get_client_ip(request)
        assert ip == "127.0.0.1"


class TestRateLimitDependency:
    """Test rate_limit_dependency function"""

    @pytest.mark.asyncio
    async def test_rate_limit_dependency_allows_under_limit(self):
        """Test rate limit dependency allows requests under limit"""
        from httpx import AsyncClient, ASGITransport
        
        app = FastAPI()
        rate_limiter = RateLimiter()
        
        @app.get("/api/data")
        async def get_data(
            _=pytest.importorskip("fastapi").Depends(
                rate_limit_dependency(rate_limiter, "10/second")
            )
        ):
            return {"data": "success"}
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # First request should succeed
            response = await client.get("/api/data")
            assert response.status_code == 200
            assert response.json() == {"data": "success"}

    @pytest.mark.asyncio
    async def test_rate_limit_dependency_rejects_over_limit(self):
        """Test rate limit dependency rejects when over limit"""
        from httpx import AsyncClient, ASGITransport
        
        app = FastAPI()
        rate_limiter = RateLimiter()
        
        @app.get("/api/data")
        async def get_data(
            _=pytest.importorskip("fastapi").Depends(
                rate_limit_dependency(rate_limiter, "2/second")
            )
        ):
            return {"data": "success"}
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # First 2 should succeed
            assert (await client.get("/api/data")).status_code == 200
            assert (await client.get("/api/data")).status_code == 200
            
            # Third should be rate limited
            response = await client.get("/api/data")
            assert response.status_code == 429
            assert "Rate limit exceeded" in response.json()["detail"]
            assert "Retry-After" in response.headers

    @pytest.mark.asyncio
    async def test_rate_limit_dependency_uses_client_ip(self):
        """Test rate limit is applied per client IP"""
        from httpx import AsyncClient, ASGITransport
        
        app = FastAPI()
        rate_limiter = RateLimiter()
        
        @app.get("/api/data")
        async def get_data(
            _=pytest.importorskip("fastapi").Depends(
                rate_limit_dependency(rate_limiter, "1/second")
            )
        ):
            return {"data": "success"}
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # First request should succeed
            response1 = await client.get("/api/data")
            assert response1.status_code == 200
            
            # Second request from same IP should be limited
            response2 = await client.get("/api/data")
            assert response2.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_dependency_with_proxy_headers(self):
        """Test rate limiting works with proxy headers"""
        from httpx import AsyncClient, ASGITransport
        
        app = FastAPI()
        rate_limiter = RateLimiter()
        
        @app.get("/api/data")
        async def get_data(
            _=pytest.importorskip("fastapi").Depends(
                rate_limit_dependency(rate_limiter, "1/second")
            )
        ):
            return {"data": "success"}
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Request with X-Forwarded-For header
            response = await client.get(
                "/api/data",
                headers={"X-Forwarded-For": "192.168.1.100"}
            )
            assert response.status_code == 200
            
            # Second request should be limited
            response2 = await client.get(
                "/api/data",
                headers={"X-Forwarded-For": "192.168.1.100"}
            )
            assert response2.status_code == 429


class TestFastAPIIntegration:
    """Integration tests combining multiple patterns"""

    @pytest.mark.asyncio
    async def test_combined_load_shedding_and_rate_limiting(self):
        """Test combining load shedding and rate limiting"""
        from httpx import AsyncClient, ASGITransport
        
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=10))
        rate_limiter = RateLimiter()
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
        
        @app.get("/api/data")
        async def get_data(
            _=pytest.importorskip("fastapi").Depends(
                rate_limit_dependency(rate_limiter, "5/second")
            )
        ):
            return {"data": "success"}
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Should pass both load shedding and rate limiting
            response = await client.get("/api/data")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_multiple_endpoints_with_different_limits(self):
        """Test multiple endpoints with different rate limits"""
        from httpx import AsyncClient, ASGITransport
        
        app = FastAPI()
        rate_limiter = RateLimiter()
        
        @app.get("/api/free")
        async def free_endpoint(
            _=pytest.importorskip("fastapi").Depends(
                rate_limit_dependency(rate_limiter, "10/second")
            )
        ):
            return {"tier": "free"}
        
        @app.get("/api/premium")
        async def premium_endpoint(
            _=pytest.importorskip("fastapi").Depends(
                rate_limit_dependency(rate_limiter, "100/second")
            )
        ):
            return {"tier": "premium"}
        
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Both should work initially
            assert (await client.get("/api/free")).status_code == 200
            assert (await client.get("/api/premium")).status_code == 200

    def test_error_handling_in_middleware(self):
        """Test middleware handles errors gracefully"""
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=10))
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
        
        @app.get("/error")
        async def error_endpoint():
            raise Exception("Unexpected error")
        
        with TestClient(app) as client:
            # Should handle error and still release resources
            with pytest.raises(Exception):
                client.get("/error")
            
            # Load shedder should be clean
            assert load_shedder.active_requests == 0

    def test_concurrent_requests_with_middleware(self):
        """Test middleware handles concurrent requests correctly"""
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=5))
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
        
        @app.get("/test")
        async def test_endpoint():
            await asyncio.sleep(0.01)
            return {"status": "ok"}
        
        with TestClient(app) as client:
            # Multiple requests should work up to limit
            responses = [client.get("/test") for _ in range(3)]
            
            # Should have some successes
            success_count = sum(1 for r in responses if r.status_code == 200)
            assert success_count > 0


class TestMiddlewareEdgeCases:
    """Test edge cases in middleware"""

    def test_middleware_with_streaming_response(self):
        """Test middleware works with streaming responses"""
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=10))
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
        
        @app.get("/stream")
        async def stream_endpoint():
            async def generate():
                for i in range(3):
                    yield f"data: {i}\n"
            
            from starlette.responses import StreamingResponse
            return StreamingResponse(generate(), media_type="text/event-stream")
        
        with TestClient(app) as client:
            response = client.get("/stream")
            
            assert response.status_code == 200
            # Load should be released after response
            assert load_shedder.active_requests == 0

    @pytest.mark.skip(reason="Requires python-multipart which is optional")
    def test_middleware_with_file_upload(self):
        """Test middleware handles file uploads"""
        pytest.importorskip("multipart")  # Skip if python-multipart not installed
        
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=10))
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
        
        @app.post("/upload")
        async def upload_file(file: bytes = pytest.importorskip("fastapi").File(...)):
            return {"size": len(file)}
        
        with TestClient(app) as client:
            response = client.post(
                "/upload",
                files={"file": ("test.txt", b"test content", "text/plain")}
            )
            
            assert response.status_code == 200
            assert load_shedder.active_requests == 0

    def test_middleware_preserves_response_headers(self):
        """Test middleware preserves custom response headers"""
        app = FastAPI()
        load_shedder = LoadShedder(config=LoadSheddingConfig(max_requests=10))
        
        app.add_middleware(LoadSheddingMiddleware, load_shedder=load_shedder)
        
        @app.get("/headers")
        async def headers_endpoint():
            from fastapi import Response
            response = Response(content="test")
            response.headers["X-Custom-Header"] = "test-value"
            return response
        
        with TestClient(app) as client:
            response = client.get("/headers")
            
            assert response.status_code == 200
            assert "X-Custom-Header" in response.headers
            assert response.headers["X-Custom-Header"] == "test-value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
