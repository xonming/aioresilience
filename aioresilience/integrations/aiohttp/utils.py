"""
Utility functions for aiohttp integration
"""


def get_client_ip(request) -> str:
    """
    Extract client IP address from aiohttp request with proxy support.
    
    Args:
        request: aiohttp Request object
        
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
    peername = request.transport.get_extra_info('peername') if request.transport else None
    if peername:
        return peername[0]
    
    return "unknown"
