"""Token symbol → logo file mapping.

Logos live in the project's `logos/` directory and are committed to git so
they're available on the deployed app.
"""
from pathlib import Path
from typing import Optional

LOGOS_DIR = Path(__file__).parent.parent / "logos"

# Default mapping: SYMBOL (uppercase) → filename in logos/
LOGO_MAP = {
    "PLS":     "PLS.png",
    "PLSX":    "PLSX.png",
    "INC":     "INC.png",
    "HEX":     "HEX.png",        # default to PulseChain HEX
    "EHEX":    "eHEX.png",
    "PRVX":    "prvx_logo.webp",
    "PROVEX":  "ProveX.jpg",
}

# Per-chain overrides: same symbol can render different logo per chain.
# Key: (UPPER_SYMBOL, lowercase_chain) → filename
CHAIN_OVERRIDES = {
    ("HEX", "ethereum"): "eHEX.png",     # bridged HEX uses eHEX logo
}


def get_logo_path(symbol: Optional[str], chain: str = "") -> Optional[str]:
    """Return absolute path to a logo file, or None if not found."""
    if not symbol:
        return None
    key = symbol.upper().strip()
    chain_key = (chain or "").lower().strip()

    # Chain-specific override first
    fname = CHAIN_OVERRIDES.get((key, chain_key))
    if not fname:
        fname = LOGO_MAP.get(key)
    if not fname:
        return None
    path = LOGOS_DIR / fname
    return str(path) if path.exists() else None


def available_symbols() -> list[str]:
    """List of all symbols we have logos for."""
    return sorted(LOGO_MAP.keys())
