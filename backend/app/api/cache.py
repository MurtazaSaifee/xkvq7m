"""Cache headers for answers that only change with a deployment."""

from fastapi import Response

# The snapshot is fixed within a deployment, so a successful answer can be cached for a day at the
# edge. Browsers keep it for five minutes. Vercel's edge cache belongs to the deployment, so a
# redeploy serves fresh data.
IMMUTABLE_CACHE_CONTROL = "public, max-age=300, s-maxage=86400"


def cache_immutable_answer(response: Response) -> None:
    """A route dependency that sets the cache header on the answer the route returns.

    FastAPI merges the header into a normal answer only. An error raised by the route is answered
    by its handler, which does not carry it, so errors are never cached.
    """
    response.headers["Cache-Control"] = IMMUTABLE_CACHE_CONTROL
