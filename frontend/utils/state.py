"""
frontend/utils/state.py
========================
State managers for the modular Streamlit compliance app.
"""

import streamlit as st
from frontend.utils.api_client import APIClient

def init_session_state():
    """
    Guarantees key state properties exist in session_state across runs.
    """
    if "api_client" not in st.session_state:
        st.session_state.api_client = APIClient()

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
        
    if "active_producer" not in st.session_state:
        st.session_state.active_producer = "GREENPACK-001"
        
    if "active_month" not in st.session_state:
        st.session_state.active_month = "2026-04"
