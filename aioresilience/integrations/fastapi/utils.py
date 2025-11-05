"""
Utility functions for FastAPI integration
"""

from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request with proxy support.
    
    Checks headers in order:
    1. X-Forwarded-For (from proxy)
    2. X-Real-IP (from nginx)
    3. Direct connection IP
    
    Args:
        request: FastAPI Request object
        
    Returns:
        Client IP address string
    """
    # Check for forwarded headers first
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    
    # Fallback to direct connection IP
    if hasattr(request, "client") and request.client:
        return request.client.host
    
    return "unknown"
