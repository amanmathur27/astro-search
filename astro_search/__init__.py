"""AstroSearch — domain-specific astronomy search engine (100% free sources)."""
import os as _os
from pathlib import Path as _Path

def _load_dotenv():
    # stdlib .env loader: repo root / cwd, env vars always win (Actions secrets unaffected)
    for cand in (_Path.cwd() / ".env", _Path(__file__).resolve().parent.parent / ".env"):
        try:
            if cand.is_file():
                for line in cand.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        _os.environ.setdefault(k.strip(), v.strip().strip("'\""))
                break
        except Exception:
            pass

_load_dotenv()
from .core import AstroSearch
from .tools import TOOL_DECLARATIONS, tool_handler

try:
    from .sources.fetch import fetch_article
except Exception:  # allow partial installs during scaffold
    fetch_article = None  # type: ignore

__all__ = ["AstroSearch", "TOOL_DECLARATIONS", "tool_handler", "fetch_article"]
__version__ = "2.1.0"
