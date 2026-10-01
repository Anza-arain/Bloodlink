"""Vercel entrypoint for the BloodLink FastAPI application."""
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from main import app

__all__ = ["app"]
