"""DRF customizations shared across the API."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from leaderboard.image_utils import DecodeBusy


def api_exception_handler(exc, context):
    """Render framework errors as `{"error": ...}` to match our explicit responses.

    DRF defaults to `{"detail": ...}` for 404/403/validation/throttle errors; this
    rewrites that single key so the frontend has one error shape everywhere. Field-level
    form errors (e.g. registration's `{"errors": {...}}`) are produced explicitly by
    views and never reach this handler.
    """
    if isinstance(exc, DecodeBusy):
        # Every image-decode slot on the instance was busy. This is a capacity
        # limit, not a bad request: 503 (plus Retry-After) is what tells the
        # client, and any crawler, that the same request is worth repeating.
        # Decoding anyway is what the slot exists to prevent — see DecodeBusy.
        return Response(
            {"error": "Server právě zpracovává jiné obrázky. Zkus to prosím za chvíli."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
            # Roughly one decode cycle. It is a hint, not a promise, but a
            # number in the right order of magnitude is what makes a client
            # retry sensibly instead of hammering or giving up.
            headers={"Retry-After": "3"},
        )

    response = exception_handler(exc, context)
    if response is not None and isinstance(response.data, dict) and "detail" in response.data:
        response.data = {"error": response.data["detail"]}
    return response
