"""Unified UI theme: CSS injection + Altair chart theme + reusable components.

Synthesizes:
  - web-design-guidelines (Vercel): tabular-nums, text-wrap balance, ellipsis (…),
    keyboard focus, reduced-motion, semantic colors
  - scientific-visualization: colorblind-safe palette, despined charts,
    consistent typography, no chart junk
  - finance-psychology: avoid 'budget' framing, positive language for savings,
    color discipline that doesn't shame negative numbers

Call `apply_app_chrome()` at the top of every page.
"""
from contextlib import contextmanager
from typing import Optional

import altair as alt
import streamlit as st


# ─── PALETTE ────────────────────────────────────────────────────────
# Anchored on emerald (savings/positive). Categorical colors are warm
# and distinguishable by all common types of color blindness (Okabe-Ito-adjacent).
PALETTE = {
    # Categorical (charts, badges)
    "income":     "#3b82f6",   # blue 500
    "bills":      "#ef4444",   # red 500
    "bnpl":       "#f97316",   # orange 500
    "envelopes":  "#eab308",   # yellow 500
    "savings":    "#10b981",   # emerald 500 — primary accent
    "guilt_free": "#22c55e",   # green 500

    # Semantic (status badges, alerts)
    "ok":      "#10b981",
    "warn":    "#f59e0b",      # amber 500
    "over":    "#ef4444",
    "muted":   "#64748b",      # slate 500

    # Surface (cards, dividers)
    "surface":         "#ffffff",
    "surface_subtle":  "#f8fafc",   # slate-50
    "surface_2":       "#f1f5f9",   # slate-100
    "border":          "#e2e8f0",   # slate-200
    "text_primary":    "#0f172a",   # slate-900
    "text_secondary":  "#475569",   # slate-600
    "text_muted":      "#94a3b8",   # slate-400
}

CATEGORICAL_DOMAIN = ["Bills", "BNPL", "Envelopes", "Savings", "Guilt-free"]
CATEGORICAL_RANGE = [
    PALETTE["bills"], PALETTE["bnpl"], PALETTE["envelopes"],
    PALETTE["savings"], PALETTE["guilt_free"],
]


# ─── CSS — injected once per page via apply_app_chrome() ────────────
_CSS = """
<style>
/* ── Typography ───────────────────────────────────────────────── */
html, body, [class*="css"], [data-testid="stMarkdownContainer"] {
    font-feature-settings: "tnum" 1, "cv11" 1;  /* tabular nums + Inter alt 1 */
}

/* Apply tabular-nums to every metric value so currency columns align */
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"],
[data-testid="stMetricLabel"] {
    font-variant-numeric: tabular-nums;
}

/* Tabular nums inside dataframes too */
.stDataFrame, .stDataFrame * {
    font-variant-numeric: tabular-nums;
}

/* Balance headings so they don't break awkwardly */
h1, h2, h3 {
    text-wrap: balance;
    letter-spacing: -0.015em;
}
h1 { font-weight: 700; }
h2 { font-weight: 650; }
h3 { font-weight: 600; }

/* ── Metric cards — subtle elevation ──────────────────────────── */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 16px 20px;
    transition: border-color 120ms ease, box-shadow 120ms ease;
}
[data-testid="stMetric"]:hover {
    border-color: #cbd5e1;
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04), 0 1px 2px rgba(15, 23, 42, 0.03);
}
[data-testid="stMetricValue"] {
    font-size: 1.875rem !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    letter-spacing: -0.025em;
}
[data-testid="stMetricLabel"] p {
    font-size: 0.8125rem !important;
    color: #64748b !important;
    font-weight: 500 !important;
    text-transform: none;
}

/* ── Buttons — refined ────────────────────────────────────────── */
.stButton button {
    border-radius: 8px;
    font-weight: 500;
    transition: transform 80ms ease, box-shadow 120ms ease;
}
.stButton button:hover {
    box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
}
.stButton button:active {
    transform: translateY(1px);
}

/* Primary button uses our emerald accent */
.stButton button[kind="primary"] {
    background: #10b981;
    border: 1px solid #059669;
}
.stButton button[kind="primary"]:hover {
    background: #059669;
    border-color: #047857;
}

/* ── Expanders — cleaner card look ────────────────────────────── */
.streamlit-expanderHeader, [data-testid="stExpander"] details summary {
    font-weight: 500;
    border-radius: 10px;
}
[data-testid="stExpander"] {
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    background: #ffffff;
}
[data-testid="stExpander"] details summary:hover {
    background: #f8fafc;
}

/* ── Dataframes — subtle borders ──────────────────────────────── */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* ── Sidebar — tighter spacing ────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #f8fafc;
    border-right: 1px solid #e2e8f0;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
    font-weight: 500;
}

/* ── Status pill component (created via st.markdown) ──────────── */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}
.status-pill.ok   { background: #d1fae5; color: #065f46; }
.status-pill.warn { background: #fef3c7; color: #92400e; }
.status-pill.over { background: #fee2e2; color: #991b1b; }
.status-pill.info { background: #dbeafe; color: #1e40af; }

/* ── Section header component ─────────────────────────────────── */
.section-header {
    display: flex;
    align-items: baseline;
    gap: 10px;
    margin-top: 8px;
    margin-bottom: 4px;
}
.section-header .emoji { font-size: 1.5rem; line-height: 1; }
.section-header .title {
    font-size: 1.375rem;
    font-weight: 650;
    color: #0f172a;
    letter-spacing: -0.015em;
}
.section-header .subtitle {
    color: #64748b;
    font-size: 0.875rem;
    margin-left: auto;
    font-weight: 500;
}

/* ── Reduced motion respect (a11y) ────────────────────────────── */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }
}

/* ── Hide Streamlit chrome we don't need ──────────────────────── */
#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
[data-testid="stToolbar"] { display: none; }
</style>
"""


# ─── ALTAIR THEME ───────────────────────────────────────────────────
def _budget_altair_theme():
    """Registered as 'budget' — applied to every chart on every page."""
    return {
        "config": {
            "view": {"continuousWidth": 400, "continuousHeight": 280, "strokeWidth": 0},
            "background": "transparent",
            "font": "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
            "padding": {"top": 6, "right": 6, "bottom": 6, "left": 6},
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
                "gridColor": PALETTE["surface_2"],
                "gridDash": [2, 2],
                "domain": False,
                "ticks": False,
                "labelPadding": 6,
            },
            "axisX": {"grid": False},  # vertical gridlines = chart junk
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
            "bar": {"cornerRadiusEnd": 4},
            "line": {"strokeWidth": 2.5},
            "area": {"opacity": 0.85},
            "arc": {"innerRadius": 60, "cornerRadius": 3, "padAngle": 0.015},
            "header": {
                "labelColor": PALETTE["text_secondary"],
                "titleColor": PALETTE["text_primary"],
            },
        }
    }


# ─── PUBLIC API ─────────────────────────────────────────────────────
_THEME_REGISTERED = False


def apply_app_chrome(page_title: str = "Budget", page_icon: str = "💰"):
    """Call at the top of every page. Sets page config, injects CSS, enables Altair theme."""
    st.set_page_config(page_title=page_title, page_icon=page_icon, layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)
    global _THEME_REGISTERED
    if not _THEME_REGISTERED:
        alt.themes.register("budget", _budget_altair_theme)
        _THEME_REGISTERED = True
    alt.themes.enable("budget")


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


def divider():
    """Thinner divider than st.markdown('---')."""
    st.markdown(
        '<hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0 16px 0;" />',
        unsafe_allow_html=True,
    )


@contextmanager
def section(emoji: str, title: str, subtitle: Optional[str] = None):
    """Context manager: section header + divider on enter, vertical spacing on exit."""
    divider()
    section_header(emoji, title, subtitle)
    yield
    st.markdown('<div style="height: 4px;"></div>', unsafe_allow_html=True)
