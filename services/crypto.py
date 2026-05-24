"""Crypto portfolio: fetches wallet balances + USD prices for PulseChain + Ethereum.

Public APIs used (no auth required for PulseChain; Etherscan needs a free key):
  - PulseChain Scan (Blockscout):  https://api.scan.pulsechain.com/api
  - Etherscan:                     https://api.etherscan.io/api  (free API key)
  - DexScreener:                   https://api.dexscreener.com/latest/dex/tokens/{address}

Cached per-render via Streamlit caching to avoid hammering APIs.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import requests
import streamlit as st

# ─── Endpoints ──────────────────────────────────────────────────────
PULSE_SCAN_API = "https://api.scan.pulsechain.com/api"
ETHERSCAN_API = "https://api.etherscan.io/api"
DEXSCREENER_API = "https://api.dexscreener.com/latest/dex/tokens"

# Native token addresses use a sentinel (real wrapped contracts have different addrs)
NATIVE_PLS = "native_pls"
NATIVE_ETH = "native_eth"

# Wrapped equivalents (for price lookup via DexScreener)
WPLS_ADDRESS = "0xA1077a294dDE1B09bB078844df40758a5D0f9a27"
WETH_ADDRESS = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

REQUEST_TIMEOUT = 10  # seconds


# ─── Data classes ──────────────────────────────────────────────────
@dataclass
class TokenHolding:
    chain: str                  # 'pulsechain' | 'ethereum'
    address: str                # token contract address (or NATIVE_*)
    symbol: str
    name: str
    balance: float              # human-readable units (already divided by 10^decimals)
    decimals: int = 18
    usd_price: Optional[float] = None
    usd_value: Optional[float] = None
    wallet_label: str = ""


@dataclass
class WalletInput:
    label: str
    address: str
    chain: str                  # 'pulsechain' | 'ethereum'


@dataclass
class PortfolioSnapshot:
    holdings: List[TokenHolding] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def total_usd(self) -> float:
        return round(sum(h.usd_value or 0 for h in self.holdings), 2)

    @property
    def by_chain(self) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for h in self.holdings:
            out[h.chain] = out.get(h.chain, 0.0) + (h.usd_value or 0.0)
        return {k: round(v, 2) for k, v in out.items()}

    @property
    def by_token(self) -> List[Tuple[str, float]]:
        agg: Dict[str, float] = {}
        for h in self.holdings:
            agg[h.symbol] = agg.get(h.symbol, 0.0) + (h.usd_value or 0.0)
        return sorted(agg.items(), key=lambda x: -x[1])


# ─── Address validation ────────────────────────────────────────────
def is_valid_address(addr: str) -> bool:
    """Basic EVM address check: 0x + 40 hex chars."""
    if not isinstance(addr, str):
        return False
    if not addr.startswith("0x"):
        return False
    if len(addr) != 42:
        return False
    try:
        int(addr[2:], 16)
        return True
    except ValueError:
        return False


# ─── Chain queries ─────────────────────────────────────────────────
def _fetch_pulsechain_balance(address: str) -> Tuple[float, Optional[str]]:
    """Native PLS balance in PLS units. Returns (balance, error_msg)."""
    try:
        r = requests.get(
            PULSE_SCAN_API,
            params={"module": "account", "action": "balance", "address": address},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "1":
            return 0.0, data.get("message", "unknown error")
        wei = int(data["result"])
        return wei / 1e18, None
    except Exception as e:
        return 0.0, f"PulseChain RPC error: {e}"


def _fetch_pulsechain_tokens(address: str) -> Tuple[List[Dict], Optional[str]]:
    """List of PRC-20 token balances. Returns (rows, error_msg)."""
    try:
        r = requests.get(
            PULSE_SCAN_API,
            params={"module": "account", "action": "tokenlist", "address": address},
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "1":
            # Empty wallet returns status=0 with "No tokens found" — treat as success
            msg = (data.get("message") or "").lower()
            if "no tokens" in msg or "not found" in msg:
                return [], None
            return [], data.get("message", "unknown error")
        return data.get("result", []), None
    except Exception as e:
        return [], f"PulseChain RPC error: {e}"


def _fetch_ethereum_balance(address: str, api_key: str) -> Tuple[float, Optional[str]]:
    """Native ETH balance. Requires an Etherscan API key."""
    if not api_key:
        return 0.0, "ETHERSCAN_API_KEY not configured"
    try:
        r = requests.get(
            ETHERSCAN_API,
            params={
                "module": "account", "action": "balance",
                "address": address, "tag": "latest", "apikey": api_key,
            },
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "1":
            return 0.0, data.get("message", "unknown error")
        wei = int(data["result"])
        return wei / 1e18, None
    except Exception as e:
        return 0.0, f"Etherscan error: {e}"


def _fetch_ethereum_tokens(address: str, api_key: str) -> Tuple[List[Dict], Optional[str]]:
    """List of ERC-20 token balances. Etherscan's tokentx returns history, not
    current holdings — we use it to find unique tokens, then query balance per token.
    For a simpler MVP we fall back to: use Etherscan's tokenbalance per token from
    the tx history. To avoid N+1 calls, we list-only the tokens here (no balance lookup).

    Returns: list of {symbol, name, contractAddress, balance} where balance comes from
    tokenbalance call. Limited to 20 most-recent unique tokens for rate-limit safety.
    """
    if not api_key:
        return [], "ETHERSCAN_API_KEY not configured"
    try:
        r = requests.get(
            ETHERSCAN_API,
            params={
                "module": "account", "action": "tokentx",
                "address": address, "sort": "desc", "apikey": api_key,
            },
            timeout=REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("status") != "1":
            msg = (data.get("message") or "").lower()
            if "no transactions" in msg:
                return [], None
            return [], data.get("message", "unknown error")
        # Get unique tokens from tx history (most recent first)
        seen: set = set()
        unique_tokens: List[Dict] = []
        for tx in data.get("result", []):
            addr = tx.get("contractAddress", "").lower()
            if addr and addr not in seen:
                seen.add(addr)
                unique_tokens.append({
                    "contractAddress": addr,
                    "symbol": tx.get("tokenSymbol", "?"),
                    "name": tx.get("tokenName", ""),
                    "decimals": int(tx.get("tokenDecimal", 18)),
                })
            if len(unique_tokens) >= 20:
                break
        # For each unique token, fetch current balance
        results: List[Dict] = []
        for tok in unique_tokens:
            try:
                br = requests.get(
                    ETHERSCAN_API,
                    params={
                        "module": "account", "action": "tokenbalance",
                        "contractaddress": tok["contractAddress"],
                        "address": address, "tag": "latest", "apikey": api_key,
                    },
                    timeout=REQUEST_TIMEOUT,
                )
                br.raise_for_status()
                bdata = br.json()
                if bdata.get("status") == "1":
                    raw_balance = int(bdata["result"])
                    balance = raw_balance / (10 ** tok["decimals"])
                    if balance > 0:
                        results.append({**tok, "balance": balance})
            except Exception:
                continue
        return results, None
    except Exception as e:
        return [], f"Etherscan error: {e}"


# ─── Pricing via DexScreener ───────────────────────────────────────
def _fetch_prices_dexscreener(addresses: List[str]) -> Dict[str, float]:
    """Batch fetch USD prices for given token contracts. Returns {address_lower: usd_price}.

    DexScreener accepts comma-separated addresses (up to 30). It returns multiple
    pairs per token; we pick the highest-liquidity pair's price.
    """
    if not addresses:
        return {}
    prices: Dict[str, float] = {}
    # Chunk to 30 per call
    for i in range(0, len(addresses), 30):
        chunk = addresses[i:i + 30]
        try:
            r = requests.get(
                f"{DEXSCREENER_API}/{','.join(chunk)}",
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            # data["pairs"] is a list; multiple per token. Track best per token.
            best: Dict[str, Tuple[float, float]] = {}  # addr -> (price, liquidity_usd)
            for pair in data.get("pairs", []) or []:
                base = pair.get("baseToken", {}).get("address", "").lower()
                price_str = pair.get("priceUsd")
                liquidity = (pair.get("liquidity") or {}).get("usd", 0)
                if not base or price_str is None:
                    continue
                try:
                    price = float(price_str)
                    liq = float(liquidity or 0)
                except (ValueError, TypeError):
                    continue
                if base not in best or liq > best[base][1]:
                    best[base] = (price, liq)
            for addr, (price, _) in best.items():
                prices[addr] = price
        except Exception:
            continue  # skip chunks that fail
    return prices


# ─── Top-level: get full portfolio ─────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def get_portfolio(
    wallets_tuple: Tuple[Tuple[str, str, str], ...],  # tuples for cache-hashing
    etherscan_api_key: str = "",
) -> PortfolioSnapshot:
    """Fetch balances + prices for the given wallets.

    wallets_tuple: tuple of (label, address, chain) — chain in {'pulsechain', 'ethereum'}.
    etherscan_api_key: optional; if empty, ethereum wallets return errors.

    Cached for 60s per (wallets, api_key) tuple.
    """
    snapshot = PortfolioSnapshot()

    # Phase 1: gather balances per wallet
    for label, address, chain in wallets_tuple:
        if not is_valid_address(address):
            snapshot.errors.append(f"{label}: invalid address")
            continue

        if chain == "pulsechain":
            pls_balance, err = _fetch_pulsechain_balance(address)
            if err:
                snapshot.errors.append(f"{label} (PulseChain): {err}")
            elif pls_balance > 0:
                snapshot.holdings.append(TokenHolding(
                    chain="pulsechain", address=NATIVE_PLS, symbol="PLS",
                    name="PulseChain", balance=pls_balance,
                    wallet_label=label,
                ))

            tokens, err = _fetch_pulsechain_tokens(address)
            if err:
                snapshot.errors.append(f"{label} (PulseChain tokens): {err}")
            for t in tokens:
                try:
                    decimals = int(t.get("decimals", 18))
                    raw = int(t.get("balance", 0))
                    if raw <= 0:
                        continue
                    snapshot.holdings.append(TokenHolding(
                        chain="pulsechain",
                        address=t.get("contractAddress", "").lower(),
                        symbol=t.get("symbol", "?"),
                        name=t.get("name", ""),
                        balance=raw / (10 ** decimals),
                        decimals=decimals,
                        wallet_label=label,
                    ))
                except (TypeError, ValueError):
                    continue

        elif chain == "ethereum":
            eth_balance, err = _fetch_ethereum_balance(address, etherscan_api_key)
            if err:
                snapshot.errors.append(f"{label} (Ethereum): {err}")
            elif eth_balance > 0:
                snapshot.holdings.append(TokenHolding(
                    chain="ethereum", address=NATIVE_ETH, symbol="ETH",
                    name="Ethereum", balance=eth_balance,
                    wallet_label=label,
                ))
            tokens, err = _fetch_ethereum_tokens(address, etherscan_api_key)
            if err:
                snapshot.errors.append(f"{label} (Ethereum tokens): {err}")
            for t in tokens:
                snapshot.holdings.append(TokenHolding(
                    chain="ethereum",
                    address=t.get("contractAddress", "").lower(),
                    symbol=t.get("symbol", "?"),
                    name=t.get("name", ""),
                    balance=t.get("balance", 0),
                    decimals=t.get("decimals", 18),
                    wallet_label=label,
                ))
        else:
            snapshot.errors.append(f"{label}: unknown chain {chain!r}")

    # Phase 2: gather prices for all unique token addresses
    addrs: List[str] = []
    for h in snapshot.holdings:
        if h.address == NATIVE_PLS:
            addrs.append(WPLS_ADDRESS.lower())
        elif h.address == NATIVE_ETH:
            addrs.append(WETH_ADDRESS.lower())
        else:
            addrs.append(h.address.lower())
    prices = _fetch_prices_dexscreener(list(set(addrs)))

    # Phase 3: hydrate holdings with prices
    for h in snapshot.holdings:
        lookup = (WPLS_ADDRESS.lower() if h.address == NATIVE_PLS
                  else WETH_ADDRESS.lower() if h.address == NATIVE_ETH
                  else h.address.lower())
        price = prices.get(lookup)
        if price is not None:
            h.usd_price = price
            h.usd_value = round(h.balance * price, 2)

    return snapshot


def get_etherscan_api_key() -> str:
    """Resolve from st.secrets → env. Returns empty string if not set."""
    try:
        if "ETHERSCAN_API_KEY" in st.secrets:
            return str(st.secrets["ETHERSCAN_API_KEY"])
    except Exception:
        pass
    return os.environ.get("ETHERSCAN_API_KEY", "")
