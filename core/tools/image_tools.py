"""Image-related tools and utilities.

The DanbooruTagMapper (core/services/danbooru_db.py) replaced the old hardcoded TAG_CATALOG.
This module re-exports it for backward compatibility and provides helpers.
"""

from ..services.danbooru_db import DanbooruTagMapper

__all__ = ["DanbooruTagMapper"]
