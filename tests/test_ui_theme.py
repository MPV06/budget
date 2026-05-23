"""Test the UI theme module — non-Streamlit-context APIs only.

apply_app_chrome() needs a live Streamlit context so we don't unit-test it;
the existing UI smoke tests cover that path.
"""
import altair as alt

from services.ui_theme import (
    PALETTE, CATEGORICAL_DOMAIN, CATEGORICAL_RANGE,
    status_pill, _budget_altair_theme,
)


def test_palette_has_required_keys():
    required = {
        "income", "bills", "bnpl", "envelopes", "savings", "guilt_free",
        "ok", "warn", "over", "muted",
        "bg", "surface", "surface_2", "border",
        "text_primary", "text_secondary", "text_muted",
    }
    assert required.issubset(set(PALETTE.keys()))


def test_categorical_domain_and_range_aligned():
    assert len(CATEGORICAL_DOMAIN) == len(CATEGORICAL_RANGE)
    assert CATEGORICAL_DOMAIN == ["Bills", "BNPL", "Envelopes", "Savings", "Guilt-free"]
    # First entry is bills (red)
    assert CATEGORICAL_RANGE[0] == PALETTE["bills"]


def test_status_pill_returns_html_with_class():
    html = status_pill("OK", "ok")
    assert 'class="status-pill ok"' in html
    assert ">OK<" in html


def test_status_pill_unknown_status_falls_back_to_info():
    html = status_pill("Whatever", "totally_made_up")
    assert "info" in html


def test_altair_theme_structure():
    theme = _budget_altair_theme()
    cfg = theme["config"]
    # Has typography
    assert "font" in cfg
    assert "Inter" in cfg["font"]
    # Axis grid is dashed (subtle) — 2-pixel dashes with 3-pixel gaps for dark mode
    assert cfg["axis"]["gridDash"] == [2, 3]
    # X axis has no grid (less visual clutter)
    assert cfg["axisX"]["grid"] is False
    # Categorical palette is wired in
    assert cfg["range"]["category"] == CATEGORICAL_RANGE
    # Bars have rounded corners
    assert cfg["bar"]["cornerRadiusEnd"] == 4


def test_theme_registers_with_altair():
    # Register manually (apply_app_chrome would do this in a Streamlit context)
    alt.themes.register("budget_test", _budget_altair_theme)
    alt.themes.enable("budget_test")
    assert alt.themes.active == "budget_test"
    alt.themes.enable("default")  # reset
