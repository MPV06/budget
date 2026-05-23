"""Unified UI theme: dark-mode CSS + Altair chart theme + reusable components.

Reference aesthetic: pulsechainstats.com (deep navy, glass-morphism cards, glowing accents).
Synthesizes:
  - web-design-guidelines (Vercel): tabular-nums, text-wrap balance, ellipsis (…),
    keyboard focus, reduced-motion, semantic colors, high contrast
  - scientific-visualization: colorblind-safe palette, despined charts, no chart junk
  - finance-psychology: positive color discipline (no shaming negative numbers)

Call `apply_app_chrome()` at the top of every page.
"""
from contextlib import contextmanager
from typing import Optional

import altair as alt
import streamlit as st


# ─── PALETTE ────────────────────────────────────────────────────────
# Dark-mode brighter accents (400-level Tailwind) so they pop on navy
PALETTE = {
    # Categorical (charts, badges) — brighter for dark backgrounds
    "income":     "#60a5fa",   # blue-400
    "bills":      "#f87171",   # red-400
    "bnpl":       "#fb923c",   # orange-400
    "envelopes":  "#fbbf24",   # amber-400
    "savings":    "#34d399",   # emerald-400 — primary accent
    "guilt_free": "#4ade80",   # green-400
    "violet":     "#a78bfa",   # violet-400 (highlights / glow)
    "cyan":       "#22d3ee",   # cyan-400 (secondary highlights)

    # Semantic (status badges, alerts)
    "ok":      "#34d399",
    "warn":    "#fbbf24",
    "over":    "#f87171",
    "muted":   "#64748b",

    # Surface (dark hierarchy)
    "bg":              "#0a0e27",   # page background — deep navy
    "surface":         "#141936",   # cards / panels
    "surface_2":       "#1c2245",   # elevated cards
    "surface_3":       "#252b4d",   # hover state
    "border":          "#252b4d",   # subtle borders
    "border_bright":   "#3b4178",   # accent borders

    # Text
    "text_primary":    "#f1f5f9",   # slate-100 — high contrast
    "text_secondary":  "#94a3b8",   # slate-400
    "text_muted":      "#64748b",   # slate-500
    "text_dim":        "#475569",   # slate-600 — backgrounds/disabled
}

CATEGORICAL_DOMAIN = ["Bills", "BNPL", "Envelopes", "Savings", "Guilt-free"]
CATEGORICAL_RANGE = [
    PALETTE["bills"], PALETTE["bnpl"], PALETTE["envelopes"],
    PALETTE["savings"], PALETTE["guilt_free"],
]


# ─── CSS — dark theme with glass-morphism cards ─────────────────────
_CSS = """
<style>
/* ── Webfont: Inter (UI) + JetBrains Mono (numerics) ─────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap');

:root {
    --font-ui: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
    --font-mono: 'JetBrains Mono', 'SF Mono', Menlo, Consolas, monospace;
}

/* ── HIDE SIDEBAR entirely — top nav replaces it ──────────────── */
[data-testid="stSidebar"],
[data-testid="stSidebarNav"],
[data-testid="stSidebarCollapseButton"],
[data-testid="collapsedControl"] {
    display: none !important;
    visibility: hidden !important;
    width: 0 !important;
}
.main, [data-testid="stAppViewContainer"] > section.main { margin-left: 0 !important; }

/* ── Page background ─────────────────────────────────────────── */
.stApp, .main {
    background:
        radial-gradient(ellipse 1200px 800px at 0% 0%, rgba(167, 139, 250, 0.06) 0%, transparent 50%),
        radial-gradient(ellipse 900px 700px at 100% 100%, rgba(52, 211, 153, 0.05) 0%, transparent 50%),
        #0a0e27;
    color: #f1f5f9;
    font-family: var(--font-ui);
}

/* Reduce default main padding now that we have top nav */
.main .block-container {
    padding-top: 1rem !important;
    padding-bottom: 4rem !important;
    max-width: 1480px;
}

/* ── Top nav bar ─────────────────────────────────────────────── */
.top-nav {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 10px 16px;
    margin: -1rem -1rem 1.25rem -1rem;
    background: rgba(10, 14, 39, 0.85);
    backdrop-filter: blur(16px) saturate(180%);
    -webkit-backdrop-filter: blur(16px) saturate(180%);
    border-bottom: 1px solid rgba(37, 43, 77, 0.7);
    position: sticky;
    top: 0;
    z-index: 999;
}
.top-nav .brand {
    font-family: var(--font-ui);
    font-size: 1.05rem;
    font-weight: 700;
    color: #f1f5f9;
    letter-spacing: -0.02em;
    margin-right: 18px;
    padding: 6px 10px;
    display: inline-flex;
    align-items: center;
    gap: 8px;
}
.top-nav .brand .dot {
    width: 8px; height: 8px; border-radius: 999px;
    background: #34d399;
    box-shadow: 0 0 8px rgba(52, 211, 153, 0.7);
}
.top-nav a.nav-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 7px 12px;
    border-radius: 8px;
    font-family: var(--font-ui);
    font-size: 0.875rem;
    font-weight: 500;
    color: #94a3b8 !important;
    text-decoration: none !important;
    transition: all 140ms ease;
    border: 1px solid transparent;
}
.top-nav a.nav-item:hover {
    color: #f1f5f9 !important;
    background: rgba(59, 65, 120, 0.4);
}
.top-nav a.nav-item.active {
    color: #34d399 !important;
    background: rgba(52, 211, 153, 0.10);
    border-color: rgba(52, 211, 153, 0.3);
}
.top-nav a.nav-item.nav-logout {
    color: #94a3b8 !important;
    margin-left: 4px;
}
.top-nav a.nav-item.nav-logout:hover {
    color: #f87171 !important;
    background: rgba(248, 113, 113, 0.10);
    border-color: rgba(248, 113, 113, 0.3);
}
.top-nav a.nav-item .emoji {
    font-size: 0.95rem;
    filter: saturate(1.2);
}
.top-nav .nav-spacer { flex: 1; }
.top-nav .nav-status {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: #64748b;
    padding: 4px 10px;
    border-radius: 999px;
    background: rgba(28, 34, 69, 0.6);
    border: 1px solid #252b4d;
    letter-spacing: 0.04em;
}

/* ── Typography ──────────────────────────────────────────────── */
html, body, [class*="css"], [data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] span {
    color: #e2e8f0 !important;
    font-family: var(--font-ui);
    font-feature-settings: "tnum" 1, "cv11" 1;
}
[data-testid="stCaptionContainer"], small {
    color: #94a3b8 !important;
}

/* Apply tabular-nums everywhere financials live */
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"],
[data-testid="stMetricLabel"],
.stDataFrame, .stDataFrame * {
    font-variant-numeric: tabular-nums;
}

/* Headings — Inter at refined sizes/weights */
h1, h2, h3, h4 {
    font-family: var(--font-ui) !important;
    text-wrap: balance;
    letter-spacing: -0.025em;
    color: #f1f5f9 !important;
    line-height: 1.2;
}
h1 { font-weight: 800; font-size: 2.25rem; margin-bottom: 0.25rem; }
h2 { font-weight: 700; font-size: 1.625rem; margin-top: 1.5rem; }
h3 { font-weight: 650; font-size: 1.25rem; color: #e2e8f0 !important; }
h4 { font-weight: 600; font-size: 1rem; color: #cbd5e1 !important; letter-spacing: -0.015em; }

/* Numerical strings use JetBrains Mono for crisper alignment */
[data-testid="stMetricValue"] > div,
.kpi-card .value {
    font-family: var(--font-mono) !important;
    font-feature-settings: "tnum" 1, "zero" 1;
}

/* ── Metric cards — glass-morphism with gradient border ────── */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, rgba(28, 34, 69, 0.6) 0%, rgba(20, 25, 54, 0.4) 100%);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border: 1px solid #252b4d;
    border-radius: 14px;
    padding: 18px 22px;
    transition: border-color 160ms ease, transform 120ms ease, box-shadow 160ms ease;
    position: relative;
    overflow: hidden;
}
[data-testid="stMetric"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(167, 139, 250, 0.4), transparent);
}
[data-testid="stMetric"]:hover {
    border-color: #3b4178;
    transform: translateY(-1px);
    box-shadow: 0 12px 24px -8px rgba(0, 0, 0, 0.3), 0 0 0 1px rgba(167, 139, 250, 0.1);
}
[data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 700 !important;
    color: #f1f5f9 !important;
    letter-spacing: -0.03em;
    line-height: 1.1;
}
[data-testid="stMetricValue"] > div { color: #f1f5f9 !important; }
[data-testid="stMetricLabel"] p {
    font-size: 0.8125rem !important;
    color: #94a3b8 !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}
[data-testid="stMetricDelta"] { font-weight: 500 !important; }
[data-testid="stMetricDelta"] svg { display: inline-block; }

/* ── Buttons ─────────────────────────────────────────────────── */
.stButton button {
    background: rgba(28, 34, 69, 0.6);
    color: #e2e8f0 !important;
    border: 1px solid #252b4d;
    border-radius: 10px;
    font-weight: 500;
    padding: 0.5rem 1rem;
    transition: all 140ms ease;
}
.stButton button:hover {
    background: rgba(59, 65, 120, 0.8);
    border-color: #3b4178;
    transform: translateY(-1px);
    box-shadow: 0 4px 12px -2px rgba(0, 0, 0, 0.3);
}
.stButton button:active { transform: translateY(0); }

/* Primary button — emerald gradient with subtle glow */
.stButton button[kind="primary"] {
    background: linear-gradient(135deg, #34d399 0%, #10b981 100%);
    color: #0a0e27 !important;
    border: 1px solid #10b981;
    font-weight: 600;
    box-shadow: 0 0 18px -4px rgba(52, 211, 153, 0.5);
}
.stButton button[kind="primary"]:hover {
    background: linear-gradient(135deg, #4ade80 0%, #22c55e 100%);
    box-shadow: 0 0 24px -2px rgba(52, 211, 153, 0.7);
}

/* ── Expanders ───────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: rgba(28, 34, 69, 0.5);
    backdrop-filter: blur(8px);
    border: 1px solid #252b4d;
    border-radius: 12px;
    margin-bottom: 8px;
}
[data-testid="stExpander"] details summary {
    color: #e2e8f0 !important;
    font-weight: 500;
    padding: 12px 16px !important;
    border-radius: 12px;
}
[data-testid="stExpander"] details summary:hover {
    background: rgba(59, 65, 120, 0.3);
}
[data-testid="stExpander"] details[open] summary {
    border-bottom: 1px solid #252b4d;
    border-radius: 12px 12px 0 0;
}

/* ── Tabs ────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 6px;
    background: transparent;
    border-bottom: 1px solid #252b4d;
}
.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: #94a3b8 !important;
    border-radius: 8px 8px 0 0;
    padding: 8px 16px;
    font-weight: 500;
}
.stTabs [data-baseweb="tab"]:hover { color: #e2e8f0 !important; background: rgba(59, 65, 120, 0.2); }
.stTabs [aria-selected="true"] {
    color: #34d399 !important;
    background: rgba(52, 211, 153, 0.08);
    border-bottom: 2px solid #34d399;
}

/* ── Dataframes ──────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
    border: 1px solid #252b4d;
    border-radius: 12px;
    overflow: hidden;
    background: rgba(20, 25, 54, 0.4);
}
[data-testid="stDataFrame"] [data-testid="stDataFrameResizable"] {
    background: transparent;
}

/* Force chart embedded text to be readable on dark bg */
.vega-embed { color: #e2e8f0 !important; }
.vega-embed .role-axis text,
.vega-embed .role-legend text,
.vega-embed .role-title text { fill: #cbd5e1 !important; }

/* ── Sidebar ─────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a0e27 0%, #0f1330 100%);
    border-right: 1px solid #252b4d;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] a {
    color: #cbd5e1 !important;
    font-weight: 500;
}
[data-testid="stSidebar"] a:hover {
    color: #34d399 !important;
}
[data-testid="stSidebarNav"] li > a[data-testid] {
    border-radius: 8px;
    padding: 6px 10px;
}

/* ── Inputs ──────────────────────────────────────────────────── */
.stTextInput input, .stNumberInput input, .stDateInput input,
.stSelectbox > div > div, .stTextArea textarea {
    background: rgba(20, 25, 54, 0.7) !important;
    color: #f1f5f9 !important;
    border: 1px solid #252b4d !important;
    border-radius: 8px !important;
}
.stTextInput input:focus, .stNumberInput input:focus,
.stDateInput input:focus, .stTextArea textarea:focus {
    border-color: #34d399 !important;
    box-shadow: 0 0 0 2px rgba(52, 211, 153, 0.2) !important;
}

/* ── Alerts (st.success / warning / error / info) ───────────── */
[data-testid="stAlert"] {
    background: rgba(20, 25, 54, 0.6) !important;
    border-radius: 12px;
    border-width: 1px;
    backdrop-filter: blur(6px);
}
[data-baseweb="notification"][kind="positive"], .stSuccess {
    background: rgba(52, 211, 153, 0.12) !important;
    border: 1px solid rgba(52, 211, 153, 0.4) !important;
    color: #d1fae5 !important;
}
[data-baseweb="notification"][kind="warning"], .stWarning {
    background: rgba(251, 191, 36, 0.10) !important;
    border: 1px solid rgba(251, 191, 36, 0.4) !important;
    color: #fef3c7 !important;
}
[data-baseweb="notification"][kind="negative"], .stError {
    background: rgba(248, 113, 113, 0.10) !important;
    border: 1px solid rgba(248, 113, 113, 0.4) !important;
    color: #fee2e2 !important;
}
[data-baseweb="notification"][kind="info"], .stInfo {
    background: rgba(96, 165, 250, 0.10) !important;
    border: 1px solid rgba(96, 165, 250, 0.4) !important;
    color: #dbeafe !important;
}

/* ── Status pill component ───────────────────────────────────── */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    border: 1px solid;
}
.status-pill.ok   {
    background: rgba(52, 211, 153, 0.12); color: #34d399;
    border-color: rgba(52, 211, 153, 0.4);
    box-shadow: 0 0 12px -2px rgba(52, 211, 153, 0.3);
}
.status-pill.warn {
    background: rgba(251, 191, 36, 0.10); color: #fbbf24;
    border-color: rgba(251, 191, 36, 0.4);
}
.status-pill.over {
    background: rgba(248, 113, 113, 0.12); color: #f87171;
    border-color: rgba(248, 113, 113, 0.4);
    box-shadow: 0 0 12px -2px rgba(248, 113, 113, 0.3);
}
.status-pill.info {
    background: rgba(96, 165, 250, 0.12); color: #60a5fa;
    border-color: rgba(96, 165, 250, 0.4);
}

/* ── Section header ──────────────────────────────────────────── */
.section-header {
    display: flex;
    align-items: baseline;
    gap: 12px;
    margin: 28px 0 12px 0;
    padding-bottom: 10px;
    border-bottom: 1px solid #252b4d;
}
.section-header .emoji { font-size: 1.6rem; line-height: 1; }
.section-header .title {
    font-size: 1.5rem;
    font-weight: 650;
    color: #f1f5f9;
    letter-spacing: -0.02em;
}
.section-header .subtitle {
    color: #94a3b8;
    font-size: 0.875rem;
    margin-left: auto;
    font-weight: 500;
}

/* ── KPI card (custom, see kpi_card()) ─────────────────────── */
.kpi-card {
    background: linear-gradient(135deg, rgba(28, 34, 69, 0.7) 0%, rgba(20, 25, 54, 0.5) 100%);
    backdrop-filter: blur(10px);
    border: 1px solid #252b4d;
    border-radius: 14px;
    padding: 20px 22px;
    position: relative;
    overflow: hidden;
    height: 100%;
}
.kpi-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent, #34d399), transparent);
}
.kpi-card .label {
    color: #94a3b8;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 8px;
}
.kpi-card .value {
    color: #f1f5f9;
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
}
.kpi-card .sub {
    color: #94a3b8;
    font-size: 0.8125rem;
    margin-top: 6px;
    font-weight: 500;
}
.kpi-card .sub.up { color: #34d399; }
.kpi-card .sub.down { color: #f87171; }

/* ── Reduced motion respect ──────────────────────────────────── */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* ── Hide Streamlit default chrome ───────────────────────────── */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
[data-testid="stDecoration"] { display: none; }

/* Horizontal rule */
hr {
    border: none;
    border-top: 1px solid #252b4d;
    margin: 24px 0;
}
</style>
"""


# ─── ALTAIR THEME ───────────────────────────────────────────────────
def _budget_altair_theme():
    """Dark Altair theme — applied to every chart automatically."""
    return {
        "config": {
            "view": {"continuousWidth": 400, "continuousHeight": 280, "strokeWidth": 0},
            "background": "transparent",
            "font": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            "padding": {"top": 8, "right": 8, "bottom": 8, "left": 8},
            "title": {
                "color": PALETTE["text_primary"],
                "fontSize": 14,
                "fontWeight": 600,
                "anchor": "start",
                "offset": 8,
            },
            "axis": {
                "labelColor": PALETTE["text_secondary"],
                "labelFontSize": 11,
                "titleColor": PALETTE["text_secondary"],
                "titleFontSize": 12,
                "titleFontWeight": 500,
                "titlePadding": 10,
                "grid": True,
                "gridColor": "rgba(148, 163, 184, 0.12)",
                "gridDash": [2, 3],
                "domain": False,
                "ticks": False,
                "labelPadding": 6,
            },
            "axisX": {"grid": False},  # no vertical gridlines
            "legend": {
                "labelColor": PALETTE["text_secondary"],
                "labelFontSize": 11,
                "titleColor": PALETTE["text_primary"],
                "titleFontSize": 12,
                "titleFontWeight": 500,
                "symbolType": "circle",
                "symbolSize": 110,
                "orient": "bottom",
                "padding": 8,
            },
            "range": {"category": CATEGORICAL_RANGE},
            "bar": {"cornerRadiusEnd": 4, "stroke": None},
            "line": {"strokeWidth": 2.5},
            "area": {"opacity": 0.85},
            "arc": {"innerRadius": 60, "cornerRadius": 3, "padAngle": 0.015, "stroke": "#0a0e27", "strokeWidth": 2},
            "rule": {"stroke": "rgba(148, 163, 184, 0.4)"},
            "point": {"size": 80, "filled": True},
            "header": {
                "labelColor": PALETTE["text_secondary"],
                "titleColor": PALETTE["text_primary"],
            },
        }
    }


# ─── NAVIGATION ─────────────────────────────────────────────────────
# Single source of truth for the nav menu — used by top_nav()
# Each entry: (route_path, label, emoji, page_file_relative_to_app)
NAV_ITEMS = [
    ("/",                 "Home",       "🏠", "app.py"),
    ("/Dashboard",        "Dashboard",  "📊", "pages/1_Dashboard.py"),
    ("/Bills",            "Bills",      "🧾", "pages/2_Bills.py"),
    ("/Envelopes",        "Envelopes",  "✉️", "pages/3_Envelopes.py"),
    ("/BNPL",             "BNPL",       "💳", "pages/4_BNPL.py"),
    ("/Save",             "Save",       "💎", "pages/10_Save.py"),
    ("/Goals",            "Goals",      "🎯", "pages/5_Goals.py"),
    ("/Emergency_Fund",   "Emergency",  "🛡️", "pages/8_Emergency_Fund.py"),
    ("/Debt",             "Debt",       "⚖️", "pages/9_Debt.py"),
    ("/Transactions",     "Activity",   "📜", "pages/6_Transactions.py"),
    ("/Settings",         "Settings",   "⚙️", "pages/7_Settings.py"),
]


def top_nav(current: str = "", show_logout: bool = False):
    """Render the top navigation using st.button + st.switch_page.

    Why buttons instead of raw <a href> or st.page_link:
    - Raw anchors trigger a full browser reload that can drop session_state
      (and thus the auth session).
    - st.page_link doesn't work for the main entry script (app.py) — it
      raises KeyError 'url_pathname'.
    - st.button + st.switch_page works for BOTH main app and pages, and
      preserves session_state because navigation stays inside Streamlit's runtime.

    show_logout: append a Sign-out button.
    """
    # Brand mark + status row above the nav
    st.markdown(
        '<div class="brand-row">'
        '<div class="brand"><span class="dot"></span>Budget</div>'
        '<div class="nav-status">LOCAL · 127.0.0.1</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    n_items = len(NAV_ITEMS) + (1 if show_logout else 0)
    cols = st.columns(n_items, gap="small")

    for i, (path, label, emoji, page_file) in enumerate(NAV_ITEMS):
        with cols[i]:
            is_active = (path == current)
            btn_type = "primary" if is_active else "secondary"
            if st.button(
                f"{emoji} {label}",
                key=f"_nav_{path}",
                type=btn_type,
                use_container_width=True,
            ):
                # Don't re-switch if already on the page
                if not is_active:
                    st.switch_page(page_file)

    if show_logout:
        with cols[-1]:
            if st.button(
                "🚪 Sign out",
                key="_nav_logout_btn",
                type="secondary",
                use_container_width=True,
            ):
                from services.auth import logout
                logout()

# ─── PUBLIC API ─────────────────────────────────────────────────────
_THEME_REGISTERED = False


def apply_app_chrome(page_title: str = "Budget", page_icon: str = "💰",
                     current_nav: str = ""):
    """Call at the top of every page.

    Args:
        page_title: browser tab title
        page_icon: tab favicon emoji
        current_nav: route path of current page (e.g. '/Dashboard') to highlight in nav

    Side effects:
        - Sets page config, injects CSS, enables Altair theme.
        - Enforces authentication via services.auth.require_auth() — if not
          authenticated, renders login form and st.stop()s the page.
        - Handles ?logout=1 query param to sign out from any nav link.
        - Renders top nav with Sign-out item once authenticated.
    """
    st.set_page_config(
        page_title=page_title,
        page_icon=page_icon,
        layout="wide",
        initial_sidebar_state="collapsed",  # double-belt: also hidden via CSS
    )
    st.markdown(_CSS, unsafe_allow_html=True)
    global _THEME_REGISTERED
    if not _THEME_REGISTERED:
        alt.themes.register("budget", _budget_altair_theme)
        _THEME_REGISTERED = True
    alt.themes.enable("budget")

    # ── Authentication gate ──
    # Handle logout query param first (so nav-link click signs us out)
    try:
        qp = st.query_params
        if qp.get("logout") == "1":
            from services.auth import logout
            # Clear the query string so refreshing the page doesn't loop-logout
            st.query_params.clear()
            logout()  # calls st.rerun()
    except Exception:
        pass

    from services.auth import require_auth
    require_auth()  # st.stop()s if unauthenticated

    # ── Authenticated — render the nav with Sign-out ──
    top_nav(current=current_nav, show_logout=True)


def section_header(emoji: str, title: str, subtitle: Optional[str] = None):
    """Branded section header — use in place of st.subheader for top-level sections."""
    sub_html = f'<span class="subtitle">{subtitle}</span>' if subtitle else ""
    st.markdown(
        f'<div class="section-header">'
        f'<span class="emoji">{emoji}</span>'
        f'<span class="title">{title}</span>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def status_pill(text: str, status: str = "info") -> str:
    """Returns HTML for a status pill. Use inside st.markdown(..., unsafe_allow_html=True).

    status: one of 'ok', 'warn', 'over', 'info'.
    """
    status_lower = status.lower()
    if status_lower not in {"ok", "warn", "over", "info"}:
        status_lower = "info"
    return f'<span class="status-pill {status_lower}">{text}</span>'


def render_status_pill(text: str, status: str = "info"):
    """Convenience: render the pill directly."""
    st.markdown(status_pill(text, status), unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: Optional[str] = None,
             accent: str = "savings", trend: Optional[str] = None):
    """Custom KPI card with gradient top border + glass-morphism background.

    accent: key from PALETTE for the top-border color
    trend: 'up' | 'down' | None  — colors the sub text
    """
    accent_color = PALETTE.get(accent, PALETTE["savings"])
    trend_class = f" {trend}" if trend in {"up", "down"} else ""
    sub_html = f'<div class="sub{trend_class}">{sub}</div>' if sub else ""
    st.markdown(
        f'<div class="kpi-card" style="--accent: {accent_color};">'
        f'<div class="label">{label}</div>'
        f'<div class="value">{value}</div>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def divider():
    """Subtle dark divider."""
    st.markdown(
        '<hr style="border: none; border-top: 1px solid #252b4d; margin: 24px 0 16px 0;" />',
        unsafe_allow_html=True,
    )


@contextmanager
def section(emoji: str, title: str, subtitle: Optional[str] = None):
    """Context manager: section header + vertical spacing."""
    section_header(emoji, title, subtitle)
    yield
    st.markdown('<div style="height: 8px;"></div>', unsafe_allow_html=True)
