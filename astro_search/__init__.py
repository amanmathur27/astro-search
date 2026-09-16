"""AstroSearch — domain-specific astronomy search engine (100% free sources)."""
from .core import AstroSearch
from .tools import TOOL_DECLARATIONS, tool_handler

try:
    from .sources.fetch import fetch_article
except Exception:  # allow partial installs during scaffold
    fetch_article = None  # type: ignore

__all__ = ["AstroSearch", "TOOL_DECLARATIONS", "tool_handler", "fetch_article"]
__version__ = "2.1.0"
