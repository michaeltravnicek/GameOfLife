"""DRF customizations shared across the API."""
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Render framework errors as `{"error": ...}` to match our explicit responses.

    DRF defaults to `{"detail": ...}` for 404/403/validation/throttle errors; this
    rewrites that single key so the frontend has one error shape everywhere. Field-level
    form errors (e.g. registration's `{"errors": {...}}`) are produced explicitly by
    views and never reach this handler.
    """
    response = exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict) and "detail" in response.data:
        response.data = {"error": response.data["detail"]}
    return response
