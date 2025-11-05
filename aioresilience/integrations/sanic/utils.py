"""
Utility functions for Sanic integration
"""


def get_client_ip(request) -> str:
    """
    Extract client IP address from Sanic request with proxy support.
    
    Args:
        request: Sanic Request object
        
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
    return request.ip or "unknown"
