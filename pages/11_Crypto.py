"""Crypto portfolio — PulseChain + Ethereum wallet auto-lookup."""
from collections import defaultdict

import altair as alt
import pandas as pd
import streamlit as st
from sqlmodel import select

from models.schema import Wallet
from services.crypto import (
    get_portfolio, is_valid_address, get_etherscan_api_key,
)
from services.db import get_session
from services.ui_theme import apply_app_chrome, PALETTE as _P, kpi_card

apply_app_chrome("Crypto — Budget", "🪙", current_nav="/Crypto")
st.markdown("# 🪙 Crypto Portfolio")
st.caption("PulseChain + Ethereum auto-discovery · Prices via DexScreener · Updates every 60s")

# ─── Load wallets + fetch portfolio ────────────────────────────────
with get_session() as session:
    wallets = session.exec(
        select(Wallet).where(Wallet.is_active == True)  # noqa: E712
    ).all()

if not wallets:
    st.info(
        "**No wallets added yet.** Add one below — paste a `0x...` address and "
        "pick the chain. PulseChain works without any API key. Ethereum requires "
        "an Etherscan API key (free at https://etherscan.io/myapikey)."
    )

# Convert to tuple for caching
wallets_tuple = tuple((w.label, w.address, w.chain) for w in wallets)
etherscan_key = get_etherscan_api_key()

snapshot = None
if wallets_tuple:
    with st.spinner("Fetching balances + prices…"):
        snapshot = get_portfolio(wallets_tuple, etherscan_api_key=etherscan_key)

# ─── KPIs + charts ────────────────────────────────────────────────
if snapshot and snapshot.holdings:
    total = snapshot.total_usd
    n_tokens = len(snapshot.holdings)
    by_chain = snapshot.by_chain
    n_chains = len(by_chain)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Total portfolio", f"${total:,.2f}", accent="savings")
    with c2:
        kpi_card("Tokens held", f"{n_tokens}",
                 sub=f"across {len(wallets)} wallet(s)", accent="violet")
    with c3:
        pls_value = by_chain.get("pulsechain", 0)
        kpi_card("PulseChain", f"${pls_value:,.2f}",
                 sub=f"{pls_value / total * 100:.0f}% of portfolio" if total else "—",
                 accent="envelopes")
    with c4:
        eth_value = by_chain.get("ethereum", 0)
        kpi_card("Ethereum", f"${eth_value:,.2f}",
                 sub=f"{eth_value / total * 100:.0f}% of portfolio" if total else "—",
                 accent="income")

    st.markdown("---")

    # ── Allocation donut by token ──
    donut_col, chain_col = st.columns([2, 1])
    with donut_col:
        st.subheader("📊 Allocation by token")
        by_token = snapshot.by_token
        top_tokens = by_token[:10]   # top 10
        other_value = sum(v for _, v in by_token[10:])
        rows = [{"token": t, "amount": v} for t, v in top_tokens]
        if other_value > 0:
            rows.append({"token": "Other", "amount": round(other_value, 2)})
        df = pd.DataFrame(rows)
        donut = (
            alt.Chart(df)
            .mark_arc(innerRadius=70, outerRadius=140,
                      cornerRadius=3, padAngle=0.02)
            .encode(
                theta=alt.Theta("amount:Q", stack=True),
                color=alt.Color("token:N",
                                legend=alt.Legend(title=None, orient="right",
                                                   labelLimit=200)),
                tooltip=["token", alt.Tooltip("amount:Q", format="$,.2f"),
                         alt.Tooltip("amount:Q", format=".1%", aggregate="sum",
                                     title="% of portfolio")],
            )
            .properties(height=350)
        )
        st.altair_chart(donut, use_container_width=True)

    with chain_col:
        st.subheader("By chain")
        chain_rows = pd.DataFrame([
            {"chain": k.title(), "value": v} for k, v in by_chain.items()
        ])
        bar = (
            alt.Chart(chain_rows)
            .mark_bar(cornerRadiusEnd=4)
            .encode(
                y=alt.Y("chain:N", title=None, sort="-x"),
                x=alt.X("value:Q", title=None, axis=alt.Axis(format="$,.0f")),
                color=alt.Color("chain:N",
                                scale=alt.Scale(domain=["Pulsechain", "Ethereum"],
                                                range=[_P["envelopes"], _P["income"]]),
                                legend=None),
                tooltip=["chain", alt.Tooltip("value:Q", format="$,.2f")],
            )
            .properties(height=350)
        )
        st.altair_chart(bar, use_container_width=True)

    st.markdown("---")

    # ── Holdings table ──
    st.subheader(f"💰 Holdings ({n_tokens})")
    sort_rows = sorted(snapshot.holdings,
                       key=lambda h: -(h.usd_value or 0))
    table_df = pd.DataFrame([{
        "symbol": h.symbol,
        "name": h.name[:30] + "…" if len(h.name) > 30 else h.name,
        "chain": h.chain.title(),
        "wallet": h.wallet_label,
        "balance": f"{h.balance:,.4f}",
        "price": f"${h.usd_price:,.6f}" if h.usd_price else "—",
        "value": f"${h.usd_value:,.2f}" if h.usd_value else "—",
        "%": f"{(h.usd_value or 0) / total * 100:.1f}%" if total else "—",
    } for h in sort_rows])
    st.dataframe(table_df, use_container_width=True, hide_index=True,
                 column_config={
                     "balance": st.column_config.TextColumn(width="medium"),
                 })

# ─── Errors ────────────────────────────────────────────────────────
if snapshot and snapshot.errors:
    with st.expander(f"⚠ {len(snapshot.errors)} warning(s) during fetch",
                     expanded=False):
        for e in snapshot.errors:
            st.warning(e)

st.markdown("---")

# ─── Wallet management ────────────────────────────────────────────
st.subheader("🔐 Wallets")

with get_session() as session:
    wallets = session.exec(select(Wallet).where(Wallet.is_active == True)).all()  # noqa: E712

    if wallets:
        for w in wallets:
            row = st.columns([3, 2, 4, 1])
            row[0].markdown(f"**{w.label}**")
            row[1].markdown(f"`{w.chain}`")
            row[2].markdown(f"`{w.address[:10]}…{w.address[-8:]}`")
            if row[3].button("🗑", key=f"del_w_{w.id}", help="Remove wallet"):
                w.is_active = False
                session.add(w); session.commit()
                # Clear the cache so the next render fetches fresh
                get_portfolio.clear()
                st.rerun()

with st.expander("➕ Add a wallet", expanded=not bool(wallets)):
    with st.form("add_wallet"):
        c1, c2, c3 = st.columns([1, 2, 1])
        label = c1.text_input("Label", value="Main",
                              help="e.g., 'Main', 'Cold storage'")
        address = c2.text_input("Address",
                                placeholder="0x...",
                                help="EVM address (works for PulseChain + Ethereum)")
        chain = c3.selectbox("Chain", ["pulsechain", "ethereum"])
        if st.form_submit_button("Add wallet", type="primary",
                                  use_container_width=True):
            if not is_valid_address(address):
                st.error("Invalid address — must be 0x followed by 40 hex chars.")
            elif not label.strip():
                st.error("Label can't be empty.")
            else:
                with get_session() as session:
                    session.add(Wallet(label=label.strip(),
                                       address=address.strip(),
                                       chain=chain, is_active=True))
                    session.commit()
                get_portfolio.clear()
                st.success(f"✓ Added {label} ({chain})")
                st.rerun()

# ─── API key status ───────────────────────────────────────────────
st.markdown("---")
st.caption(
    f"**Etherscan API key**: "
    f"{'✓ configured' if etherscan_key else '✗ not set (Ethereum wallets won\\'t fetch)'}  ·  "
    "**PulseChain**: no key needed"
)
if not etherscan_key:
    st.info(
        "To enable Ethereum wallet lookups:\n"
        "1. Get a free API key at https://etherscan.io/myapikey\n"
        "2. Add to `.env` (local) or Streamlit Cloud Secrets:\n"
        "   `ETHERSCAN_API_KEY=YOUR_KEY`\n"
        "3. Restart the app."
    )
