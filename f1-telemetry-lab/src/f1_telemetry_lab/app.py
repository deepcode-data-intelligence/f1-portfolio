"""Streamlit entry point."""

import streamlit as st

from f1_telemetry_lab import __version__
from f1_telemetry_lab.config import settings

st.set_page_config(page_title="F1 Telemetry Lab", layout="wide")
st.title("F1 Telemetry Lab")
st.caption(f"v{__version__} · historian: {settings.boxbox_url}")
st.info("Scaffold. Comparative lap dashboards (speed / throttle / brake by distance) land next.")
