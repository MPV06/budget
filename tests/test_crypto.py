"""Tests for crypto portfolio service. HTTP calls are mocked."""
from unittest.mock import patch, MagicMock

import pytest

from services.crypto import (
    is_valid_address, PortfolioSnapshot, TokenHolding,
    _fetch_pulsechain_balance, _fetch_pulsechain_tokens,
    _fetch_prices_dexscreener,
    NATIVE_PLS, NATIVE_ETH,
)


# ─── Address validation ────────────────────────────────────────────
def test_valid_eth_address():
    assert is_valid_address("0xA1077a294dDE1B09bB078844df40758a5D0f9a27") is True


def test_lowercase_address_valid():
    assert is_valid_address("0xa1077a294dde1b09bb078844df40758a5d0f9a27") is True


def test_too_short():
    assert is_valid_address("0x1234") is False


def test_missing_prefix():
    assert is_valid_address("A1077a294dDE1B09bB078844df40758a5D0f9a27") is False


def test_non_hex_chars():
    assert is_valid_address("0xZZZZ7a294dDE1B09bB078844df40758a5D0f9a27") is False


def test_none_or_empty():
    assert is_valid_address(None) is False
    assert is_valid_address("") is False
    assert is_valid_address(123) is False


# ─── PortfolioSnapshot aggregation ─────────────────────────────────
def test_snapshot_total_usd_sums_holdings():
    snap = PortfolioSnapshot(holdings=[
        TokenHolding(chain="pulsechain", address="0xa", symbol="PLS", name="x",
                     balance=1000, usd_value=50.0),
        TokenHolding(chain="ethereum", address="0xb", symbol="ETH", name="y",
                     balance=0.5, usd_value=1500.0),
    ])
    assert snap.total_usd == 1550.0


def test_snapshot_handles_missing_prices():
    snap = PortfolioSnapshot(holdings=[
        TokenHolding(chain="pulsechain", address="0xa", symbol="PLS", name="x",
                     balance=1000, usd_value=None),  # no price
        TokenHolding(chain="ethereum", address="0xb", symbol="ETH", name="y",
                     balance=0.5, usd_value=1500.0),
    ])
    assert snap.total_usd == 1500.0


def test_snapshot_by_chain_aggregates():
    snap = PortfolioSnapshot(holdings=[
        TokenHolding(chain="pulsechain", address="0xa", symbol="PLS", name="",
                     balance=1, usd_value=50.0),
        TokenHolding(chain="pulsechain", address="0xb", symbol="PLSX", name="",
                     balance=1, usd_value=25.0),
        TokenHolding(chain="ethereum", address="0xc", symbol="ETH", name="",
                     balance=1, usd_value=1500.0),
    ])
    by = snap.by_chain
    assert by["pulsechain"] == 75.0
    assert by["ethereum"] == 1500.0


def test_snapshot_by_token_sorted_descending():
    snap = PortfolioSnapshot(holdings=[
        TokenHolding(chain="pulsechain", address="0xa", symbol="PLS", name="",
                     balance=1, usd_value=50.0),
        TokenHolding(chain="ethereum", address="0xb", symbol="ETH", name="",
                     balance=1, usd_value=1500.0),
        TokenHolding(chain="pulsechain", address="0xc", symbol="PLSX", name="",
                     balance=1, usd_value=10.0),
    ])
    ranked = snap.by_token
    assert ranked[0] == ("ETH", 1500.0)
    assert ranked[1] == ("PLS", 50.0)
    assert ranked[2] == ("PLSX", 10.0)


# ─── HTTP mocks: PulseChain balance ───────────────────────────────
def _mock_response(json_data, status_code=200):
    m = MagicMock()
    m.json.return_value = json_data
    m.status_code = status_code
    m.raise_for_status = MagicMock()
    return m


def test_pulsechain_balance_happy_path_via_rpc():
    """JSON-RPC POST returns balance — Scan API never called."""
    rpc_response = _mock_response({
        "jsonrpc": "2.0", "id": 1,
        "result": hex(int(2_500 * 1e18)),  # hex-encoded wei
    })
    with patch("services.crypto.requests.post", return_value=rpc_response), \
         patch("services.crypto.requests.get") as get_mock:
        bal, err = _fetch_pulsechain_balance("0x" + "a" * 40)
        get_mock.assert_not_called()   # Scan API was never tried
    assert err is None
    assert bal == 2500.0


def test_pulsechain_balance_fallback_to_scan_when_rpc_fails():
    """All RPCs fail (500) → falls back to Scan API which succeeds."""
    rpc_fail = _mock_response({}, status_code=503)
    scan_ok = _mock_response({"status": "1", "result": str(int(2_500 * 1e18))})
    with patch("services.crypto.requests.post", return_value=rpc_fail), \
         patch("services.crypto.requests.get", return_value=scan_ok):
        bal, err = _fetch_pulsechain_balance("0x" + "a" * 40)
    assert err is None
    assert bal == 2500.0


def test_pulsechain_balance_handles_error():
    """Scan returns 'Bad address' — surface that as the error (after RPC also fails)."""
    rpc_fail = _mock_response({}, status_code=503)
    fake = _mock_response({"status": "0", "message": "Bad address"})
    with patch("services.crypto.requests.post", return_value=rpc_fail), \
         patch("services.crypto.requests.get", return_value=fake):
        bal, err = _fetch_pulsechain_balance("0xbad")
    assert bal == 0.0
    assert "Bad address" in err


def test_pulsechain_balance_handles_network_failure():
    """Both RPC and Scan fail with connection errors → unified error message."""
    with patch("services.crypto.requests.post",
               side_effect=ConnectionError("rpc-boom")), \
         patch("services.crypto.requests.get",
               side_effect=ConnectionError("scan-boom")):
        bal, err = _fetch_pulsechain_balance("0x" + "a" * 40)
    assert bal == 0.0
    assert "PulseChain unreachable" in err
    assert "rpc-boom" in err
    assert "scan-boom" in err


def test_pulsechain_tokens_empty_wallet_returns_clean():
    """No-tokens response should NOT be treated as an error."""
    fake = _mock_response({"status": "0", "message": "No tokens found"})
    with patch("services.crypto.requests.get", return_value=fake):
        rows, err = _fetch_pulsechain_tokens("0x" + "a" * 40)
    assert rows == []
    assert err is None


# ─── DexScreener pricing ──────────────────────────────────────────
def test_dexscreener_returns_highest_liquidity_price():
    """Multiple pairs per token — should pick the one with most liquidity."""
    fake = _mock_response({
        "pairs": [
            {"baseToken": {"address": "0xABC"}, "priceUsd": "1.50",
             "liquidity": {"usd": 5000}},
            {"baseToken": {"address": "0xabc"}, "priceUsd": "1.20",
             "liquidity": {"usd": 50000}},  # higher liquidity → wins
            {"baseToken": {"address": "0xDEF"}, "priceUsd": "0.05",
             "liquidity": {"usd": 1000}},
        ]
    })
    with patch("services.crypto.requests.get", return_value=fake):
        prices = _fetch_prices_dexscreener(["0xabc", "0xdef"])
    assert prices["0xabc"] == 1.20  # higher-liquidity wins
    assert prices["0xdef"] == 0.05


def test_dexscreener_empty_input_short_circuits():
    with patch("services.crypto.requests.get") as get:
        out = _fetch_prices_dexscreener([])
        assert out == {}
        get.assert_not_called()


def test_dexscreener_handles_malformed_response():
    """Garbage response should not raise — just return what it can."""
    fake = _mock_response({"pairs": [{"baseToken": {}, "priceUsd": "notanumber"}]})
    with patch("services.crypto.requests.get", return_value=fake):
        prices = _fetch_prices_dexscreener(["0xabc"])
    assert prices == {}
