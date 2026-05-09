import os

from django.conf import settings
from django.http import FileResponse, Http404
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie


@ensure_csrf_cookie
def react_index(request):
    """Serve the built React index.html for any non-API/non-admin route.

    Side effect: ensure_csrf_cookie sets the csrftoken cookie so React
    can include it in subsequent POST requests.
    """
    index_path = os.path.join(settings.STATIC_ROOT, "react", "index.html")
    if not os.path.exists(index_path):
        # Dev fallback: try the source frontend dir
        alt = os.path.join(settings.BASE_DIR.parent, "frontend", "dist", "index.html")
        if os.path.exists(alt):
            index_path = alt
        else:
            raise Http404(
                "React build not found. Run `cd frontend && npm run build` "
                "and ensure the output is collected into staticfiles/react/."
            )
    return FileResponse(open(index_path, "rb"), content_type="text/html")
