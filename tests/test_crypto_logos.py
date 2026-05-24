"""Tests for token logo lookup."""
from services.crypto_logos import (
    get_logo_path, get_logo_data_url, available_symbols,
    LOGO_MAP, CHAIN_OVERRIDES,
)


# ─── Data URL conversion ──────────────────────────────────────────
def test_data_url_returns_base64_with_correct_mime():
    url = get_logo_data_url("PLS")
    assert url is not None
    assert url.startswith("data:image/png;base64,")
    # Verify it's valid base64
    import base64
    payload = url.split(",", 1)[1]
    decoded = base64.b64decode(payload)
    # PNG magic bytes
    assert decoded[:8] == b"\x89PNG\r\n\x1a\n"


def test_data_url_handles_webp():
    url = get_logo_data_url("PRVX")
    assert url is not None
    assert url.startswith("data:image/webp;base64,")


def test_data_url_returns_none_for_unknown_symbol():
    assert get_logo_data_url("MADEUPCOIN") is None


def test_provex_alias_maps_to_webp():
    """PRVX and PROVEX should both render the same webp logo."""
    pr = get_logo_data_url("PRVX")
    pv = get_logo_data_url("PROVEX")
    assert pr is not None
    assert pv is not None
    assert pr == pv
    assert "webp" in pr


def test_data_url_chain_override_routes_correctly():
    """Verify chain override picks a different FILE for HEX on Ethereum
    (contents may match if HEX.png and eHEX.png are byte-identical)."""
    pc_path = get_logo_path("HEX", "pulsechain")
    eth_path = get_logo_path("HEX", "ethereum")
    assert pc_path != eth_path
    assert "eHEX" in eth_path
    assert "eHEX" not in pc_path
    # And both should produce valid data URLs
    assert get_logo_data_url("HEX", "pulsechain").startswith("data:image/png;base64,")
    assert get_logo_data_url("HEX", "ethereum").startswith("data:image/png;base64,")


def test_known_symbol_returns_file():
    p = get_logo_path("PLS")
    assert p is not None
    assert p.endswith("PLS.png")


def test_symbol_is_case_insensitive():
    assert get_logo_path("pls") == get_logo_path("PLS") == get_logo_path("Pls")


def test_unknown_symbol_returns_none():
    assert get_logo_path("MADEUPCOIN") is None


def test_none_and_empty_inputs():
    assert get_logo_path(None) is None
    assert get_logo_path("") is None
    assert get_logo_path("   ") is None


def test_chain_override_routes_to_alternate_logo():
    """HEX on Ethereum should use eHEX logo, not the default HEX one."""
    pc = get_logo_path("HEX", "pulsechain")
    eth = get_logo_path("HEX", "ethereum")
    assert pc is not None
    assert eth is not None
    assert "eHEX" in eth
    assert "eHEX" not in pc


def test_chain_default_when_no_override():
    """Symbols without overrides ignore the chain argument."""
    pls_pc = get_logo_path("PLS", "pulsechain")
    pls_eth = get_logo_path("PLS", "ethereum")  # even though PLS isn't on ETH
    assert pls_pc == pls_eth  # same logo regardless of chain


def test_available_symbols_returns_sorted_list():
    syms = available_symbols()
    assert syms == sorted(syms)
    assert "PLS" in syms
    assert "HEX" in syms


def test_all_mapped_logos_actually_exist_on_disk():
    """Every entry in LOGO_MAP should point to a real file."""
    from pathlib import Path
    from services.crypto_logos import LOGOS_DIR
    missing = [f for f in LOGO_MAP.values() if not (LOGOS_DIR / f).exists()]
    assert not missing, f"Missing logo files: {missing}"


def test_all_chain_overrides_exist_on_disk():
    from pathlib import Path
    from services.crypto_logos import LOGOS_DIR
    missing = [f for f in CHAIN_OVERRIDES.values() if not (LOGOS_DIR / f).exists()]
    assert not missing, f"Missing override files: {missing}"
