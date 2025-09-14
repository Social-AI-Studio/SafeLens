"""
SafeLens backend package.

This file ensures `web` is treated as a proper Python package so that
relative imports like `from .logging_config import configure_logging`
work when running the app as a module (e.g., `python -m web.server`)
or with uvicorn (`uvicorn web.server:app`).
"""

__all__ = []

