"""
frontend/main.py
=================
Modular entrypoint bootstrapping for the EcoRecon Streamlit compliance dashboard.
Ties all style blocks, utilities, states, and components together.
"""

import streamlit as st

# 1. Page settings configuration
st.set_page_config(
    page_title="EcoRecon AI — EPR Control Center",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Imports core styles and utilities
from frontend.styles.css_blocks import GLOBAL_CSS, SVG_BRANDING_BADGE
from frontend.utils.state import init_session_state
from frontend.components.analytics import render_analytics_tab
from frontend.components.ingestion import render_ingestion_tab
from frontend.components.audit import render_audit_tab
from frontend.components.policy_qa import render_policy_qa_tab

# Inject Custom Global CSS overrides
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# Initialize global session states
init_session_state()

api_client = st.session_state.api_client

# ─────────────────────────────────────────────────────────────────────────────
# 3. Sidebar Brand Badge & Health Status Monitors
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    # Render premium corporate vector branding badge
    st.markdown(SVG_BRANDING_BADGE, unsafe_allow_html=True)
    
    st.markdown("`GreenPack Industries (India)`")
    st.markdown("---")
    
    # Render clean API connection health check indicator
    is_active = api_client.check_connection()
    if is_active:
        st.markdown(
            '<div style="display:flex; align-items:center; gap:10px; padding: 10px 14px; background: rgba(16,185,129,0.08); border-radius: 8px; border: 1px solid rgba(16,185,129,0.2);">'
            '<div style="width:10px; height:10px; border-radius:50%; background:#10B981; box-shadow:0 0 10px #10B981;"></div>'
            '<span style="color:#34D399; font-weight:600; font-size:13px; font-family:\'Inter\';">API Services Active</span>'
            '</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div style="display:flex; align-items:center; gap:10px; padding: 10px 14px; background: rgba(239,68,68,0.08); border-radius: 8px; border: 1px solid rgba(239,68,68,0.2);">'
            '<div style="width:10px; height:10px; border-radius:50%; background:#EF4444; box-shadow:0 0 10px #EF4444;"></div>'
            '<span style="color:#F87171; font-weight:600; font-size:13px; font-family:\'Inter\';">FastAPI Offline</span>'
            '</div>',
            unsafe_allow_html=True
        )
        
    st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
    st.markdown("**Engine Specifications:**")
    st.markdown("- **Orchestration**: Stateful LangGraph Dynamic DAG")
    st.markdown("- **Generative LLM**: Groq llama-4-scout-17b")
    st.markdown("- **Vector Index**: ChromaDB Persistent Index")
    st.markdown("- **Embeddings Model**: Ollama nomic-embed-text")
    st.markdown("- **Validation Threshold**: $\pm$ 5% Deviation Limit")

# ─────────────────────────────────────────────────────────────────────────────
# 4. Master Layout Headers
# ─────────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="glass-card active-glow" style="display: flex; justify-content: space-between; align-items: center; padding: 20px 24px;">
        <div>
            <h1 style="margin: 0; font-size: 30px; font-weight: 800; background: linear-gradient(90deg, #10B981, #34D399); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">
                EPR Compliance Audit Center
            </h1>
            <p style="margin: 5px 0 0 0; color: #94A3B8; font-size: 13px; font-family: 'Inter';">
                Extended Producer Responsibility obligation management and narrative summary intelligence control room.
            </p>
        </div>
        <div style="text-align: right;">
            <span style="font-size: 11px; color: #64748B; display: block; font-weight: 600; letter-spacing: 0.05em; text-transform: uppercase;">Reporting Scope</span>
            <span style="font-size: 16px; font-weight: 600; color: #10B981; font-family: 'Outfit';">FY 2026-27 Active</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────────────────────
# 5. Dynamic Tab Workspace Router
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Obligation Analytics",
    "📝 submit obligation Data",
    "⚖️ Reconciliation Matrix",
    "📚 Compliance Policy QA"
])

with tab1:
    render_analytics_tab()

with tab2:
    render_ingestion_tab(api_client)

with tab3:
    render_audit_tab(api_client)

with tab4:
    render_policy_qa_tab(api_client)
