"""Token symbol → logo file mapping + base64 data URL conversion.

Logos live in the project's `logos/` directory and are committed to git so
they're available on the deployed app.

Streamlit's st.column_config.ImageColumn renders local file paths
inconsistently across deploys, so we serve them as base64 data URLs which
work universally. Conversion is lru-cached per file.
"""
import base64
from functools import lru_cache
from pathlib import Path
from typing import Optional

LOGOS_DIR = Path(__file__).parent.parent / "logos"

# Default mapping: SYMBOL (uppercase) → filename in logos/
# Both PRVX and PROVEX route to the newer .webp logo
LOGO_MAP = {
    "PLS":     "PLS.png",
    "PLSX":    "PLSX.png",
    "INC":     "INC.png",
    "HEX":     "HEX.png",            # default to PulseChain HEX
    "EHEX":    "eHEX.png",
    "PRVX":    "prvx_logo.webp",     # ProveX — uses newer logo
    "PROVEX":  "prvx_logo.webp",     # alias — same logo
}

# Per-chain overrides: same symbol can render different logo per chain.
# Key: (UPPER_SYMBOL, lowercase_chain) → filename
CHAIN_OVERRIDES = {
    ("HEX", "ethereum"): "eHEX.png",     # bridged HEX uses eHEX logo
}

# MIME types by file extension — used to build data URLs
_MIME = {
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".svg":  "image/svg+xml",
    ".gif":  "image/gif",
}


def get_logo_path(symbol: Optional[str], chain: str = "") -> Optional[str]:
    """Return absolute path to a logo file, or None if not found."""
    if not symbol:
        return None
    key = symbol.upper().strip()
    chain_key = (chain or "").lower().strip()

    fname = CHAIN_OVERRIDES.get((key, chain_key))
    if not fname:
        fname = LOGO_MAP.get(key)
    if not fname:
        return None
    path = LOGOS_DIR / fname
    return str(path) if path.exists() else None


@lru_cache(maxsize=128)
def _encode_file_to_data_url(path_str: str) -> Optional[str]:
    """Read a file from disk and return a base64 data URL. Cached."""
    p = Path(path_str)
    if not p.exists():
        return None
    mime = _MIME.get(p.suffix.lower(), "application/octet-stream")
    data = p.read_bytes()
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def get_logo_data_url(symbol: Optional[str], chain: str = "") -> Optional[str]:
    """Return a base64-encoded data URL for the symbol's logo.

    Works universally across Streamlit deploys (no filesystem-path quirks).
    Cached per file via lru_cache on the encoder.
    """
    path = get_logo_path(symbol, chain)
    if not path:
        return None
    return _encode_file_to_data_url(path)


def available_symbols() -> list[str]:
    """List of all symbols we have logos for."""
    return sorted(LOGO_MAP.keys())
