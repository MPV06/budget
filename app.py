"""Budget app entry — redirects to Dashboard after authentication.

This file exists because Streamlit needs a main entry script. Once the user
is authenticated (handled inside apply_app_chrome), we immediately hand off
to the Dashboard. Most users never see this file render.
"""
import streamlit as st

from services.ui_theme import apply_app_chrome

# Auth gate fires inside apply_app_chrome. If not authenticated, the login
# form renders and st.stop()s the script — we never reach the switch_page below.
apply_app_chrome("Budget", "💰", current_nav="/Dashboard")

# Authenticated — go straight to the Dashboard.
st.switch_page("pages/1_Dashboard.py")
