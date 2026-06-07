from fastapi import Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# TODO: Initialize a Limiter instance with a key function (e.g., client IP)
# TODO: Define default rate limit values (e.g., requests per minute/hour)
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])

# TODO: Add custom rate-limit-exceeded exception handler
def rate_limit_custom_handler(request: Request, exc: RateLimitExceeded):
    return _rate_limit_exceeded_handler(request, exc)
