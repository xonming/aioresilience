"""
Tests for FastAPI RetryMiddleware
Note: RetryMiddleware has limitations due to Starlette's call_next() behavior.
The retry_route decorator is recommended for production use.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from aioresilience import RetryPolicy, RetryConfig
from aioresilience.integrations.fastapi import RetryMiddleware


class TestRetryMiddleware:
    """Test RetryMiddleware (with known limitations)"""
    
    def test_successful_request_no_retry(self):
        """Test successful request doesn't retry"""
        app = FastAPI()
        call_count = {"count": 0}
        
        app.add_middleware(
            RetryMiddleware,
            retry_policy=RetryPolicy(config=RetryConfig(max_attempts=3, initial_delay=0.001)),
        )
        
        @app.get("/")
        async def root():
            call_count["count"] += 1
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
        # No retry on success
        assert call_count["count"] == 1
    
    def test_with_custom_policy(self):
        """Test with custom retry policy"""
        app = FastAPI()
        policy = RetryPolicy(
            config=RetryConfig(
                max_attempts=2,
                initial_delay=0.001,
                max_delay=0.01,
            )
        )
        
        app.add_middleware(
            RetryMiddleware,
            retry_policy=policy,
        )
        
        @app.get("/")
        async def root():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
    
    def test_retry_on_status_codes(self):
        """Test retry on specific status codes"""
        app = FastAPI()
        
        app.add_middleware(
            RetryMiddleware,
            retry_policy=RetryPolicy(config=RetryConfig(max_attempts=3, initial_delay=0.001)),
            retry_on_status_codes=[500, 502, 503],
        )
        
        @app.get("/")
        async def root():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
    
    def test_exclude_paths(self):
        """Test path exclusion"""
        app = FastAPI()
        
        app.add_middleware(
            RetryMiddleware,
            retry_policy=RetryPolicy(config=RetryConfig(max_attempts=3, initial_delay=0.001)),
            exclude_paths=["/health"],
        )
        
        @app.get("/api")
        async def api():
            return {"status": "ok"}
        
        @app.get("/health")
        async def health():
            return {"status": "healthy"}
        
        client = TestClient(app)
        
        assert client.get("/api").status_code == 200
        assert client.get("/health").status_code == 200
    
    def test_default_policy(self):
        """Test with default retry policy"""
        app = FastAPI()
        
        # No policy specified - uses default
        app.add_middleware(RetryMiddleware)
        
        @app.get("/")
        async def root():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get("/")
        
        assert response.status_code == 200
    
    def test_multiple_patterns(self):
        """Test middleware with different route patterns"""
        app = FastAPI()
        
        app.add_middleware(
            RetryMiddleware,
            retry_policy=RetryPolicy(config=RetryConfig(max_attempts=2, initial_delay=0.001)),
        )
        
        @app.get("/api/users")
        async def users():
            return {"users": []}
        
        @app.get("/api/users/{user_id}")
        async def user(user_id: int):
            return {"id": user_id}
        
        @app.post("/api/users")
        async def create_user():
            return {"created": True}
        
        client = TestClient(app)
        
        assert client.get("/api/users").status_code == 200
        assert client.get("/api/users/1").status_code == 200
        assert client.post("/api/users").status_code == 200
    
    def test_with_query_parameters(self):
        """Test with query parameters"""
        app = FastAPI()
        
        app.add_middleware(
            RetryMiddleware,
            retry_policy=RetryPolicy(config=RetryConfig(max_attempts=2, initial_delay=0.001)),
        )
        
        @app.get("/search")
        async def search(q: str = ""):
            return {"query": q, "results": []}
        
        client = TestClient(app)
        response = client.get("/search?q=test")
        
        assert response.status_code == 200
        assert response.json()["query"] == "test"
    
    def test_with_headers(self):
        """Test with custom headers"""
        app = FastAPI()
        
        app.add_middleware(
            RetryMiddleware,
            retry_policy=RetryPolicy(config=RetryConfig(max_attempts=2, initial_delay=0.001)),
        )
        
        @app.get("/")
        async def root():
            return {"status": "ok"}
        
        client = TestClient(app)
        response = client.get(
            "/",
            headers={"X-Custom-Header": "value"},
        )
        
        assert response.status_code == 200


class TestRetryMiddlewareLimitations:
    """Test known limitations of RetryMiddleware"""
    
    def test_middleware_limitation_note(self):
        """
        Document the limitation: RetryMiddleware cannot truly retry
        due to Starlette's call_next() consuming the request.
        
        This test exists to document the behavior.
        Use retry_route decorator for actual retry functionality.
        """
        app = FastAPI()
        
        app.add_middleware(
            RetryMiddleware,
            retry_policy=RetryPolicy(config=RetryConfig(max_attempts=3, initial_delay=0.001)),
        )
        
        call_count = {"count": 0}
        
        @app.get("/")
        async def root():
            call_count["count"] += 1
            if call_count["count"] < 3:
                raise Exception("Fail")
            return {"status": "ok"}
        
        client = TestClient(app)
        
        # Due to call_next() limitation, retry won't work as expected
        # The endpoint would need internal retry logic
        with pytest.raises(Exception):
            client.get("/")
