"""Vercel Python function: serves the FastAPI app under ``/api/*``.

Vercel runs this file with the project root as the function root. The backend package lives in
``backend/``, so that directory is put on ``sys.path`` before ``app`` is imported.
"""

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app  # noqa: E402

__all__ = ["app"]
