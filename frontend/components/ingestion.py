"""
frontend/components/ingestion.py
=================================
Monthly Packaging declaration forms and validation handshakes.
"""

import streamlit as st
from frontend.utils.api_client import APIClient

def render_ingestion_tab(api_client: APIClient):
    """
    Renders the monthly plastic obligation ingestion wizard.
    """
    st.markdown("### **EPR Plastic Declaration Submission**")
    
    st.markdown(
        """
        <div class="glass-card">
            <h5 style="margin: 0 0 8px 0; color: #10B981;">Submit Raw Monthly Packaging Obligations</h5>
            <p style="margin: 0; font-size: 13px; color: #94A3B8; line-height: 1.5;">
                Validation occurs immediately at the HTTP gateway. Non-negative bounds and month formats (YYYY-MM) are enforced deterministically before database writes.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Form layout
    with st.form("declaration_form"):
        col1, col2 = st.columns(2)
        with col1:
            producer_id = st.text_input(
                "Registered Producer ID", 
                value=st.session_state.active_producer, 
                help="Uppercase alphanumeric + hyphens (e.g. GREENPACK-001)"
            ).strip().upper()
        with col2:
            month = st.text_input(
                "Target Month (YYYY-MM)", 
                value=st.session_state.active_month, 
                help="Target period in YYYY-MM format (e.g. 2026-04)"
            ).strip()
            
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        st.markdown("##### **Obligation Breakdowns (kg)**")
        
        f1, f2, f3 = st.columns(3)
        with f1:
            rigid = st.number_input(
                "Rigid Plastic Packaging", 
                min_value=0.0, 
                max_value=10000000.0, 
                value=12000.0, 
                step=500.0
            )
        with f2:
            flexible = st.number_input(
                "Flexible Plastic Packaging", 
                min_value=0.0, 
                max_value=10000000.0, 
                value=8500.0, 
                step=500.0
            )
        with f3:
            multilayer = st.number_input(
                "Multilayer Plastic Packaging", 
                min_value=0.0, 
                max_value=10000000.0, 
                value=3200.0, 
                step=500.0
            )
            
        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
        submit_btn = st.form_submit_button("📁 Submit & Persist Obligation Record")
        
        if submit_btn:
            # client-side validations
            total = rigid + flexible + multilayer
            if total <= 0:
                st.error("Submission blocked: Total packaging weight must exceed 0.0 kg.")
            else:
                payload = {
                    "producer_id": producer_id,
                    "month": month,
                    "declared_quantities_kg": {
                        "rigid_plastic": rigid,
                        "flexible_plastic": flexible,
                        "multilayer_plastic": multilayer
                    }
                }
                
                with st.spinner("Executing edge validation checks..."):
                    status, resp = api_client.submit_declaration(payload)
                    
                    if status in (200, 201):
                        st.success(f"✓ Plastic Declaration recorded successfully! Record UUID: {resp.get('record_id')}")
                        st.session_state.active_producer = producer_id
                        st.session_state.active_month = month
                        st.json(resp)
                    elif status == 409:
                        st.warning(f"⚠️ Ingestion Conflict: {resp.get('message', 'Record already exists.')}")
                    elif status == 422:
                        # Pydantic validation details
                        st.error(f"❌ Input Validation Error (422):")
                        st.json(resp.get("detail", {}))
                    else:
                        st.error(f"❌ Server Error ({status}): {resp.get('message', 'Unspecified execution failure.')}")
