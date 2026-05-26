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
                        # Render a premium glassmorphism digital receipt card instead of raw JSON
                        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                        categories_list = resp.get("categories", [])
                        
                        # Generate HTML for a clean receipt breakdown
                        categories_rows = "".join(
                            f"""
                            <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.05);">
                                <td style="padding: 10px; font-weight: 500; color: #E2E8F0;">
                                    {cat.get('category', '').replace('_', ' ').title()}
                                </td>
                                <td style="padding: 10px; text-align: right; color: #34D399; font-weight: 600;">
                                    {cat.get('declared_quantity_kg', 0.0):,.1f} kg
                                </td>
                            </tr>
                            """
                            for cat in categories_list
                        )
                        
                        receipt_html = f"""
                        <div class="glass-card active-glow" style="border-left: 4px solid #10B981 !important; padding: 20px; border-radius: 8px; margin-top: 15px;">
                            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 12px; margin-bottom: 15px;">
                                <h5 style="margin: 0; color: #10B981; font-weight: 600; font-size: 15px;">📄 EPR Obligation Digital Receipt</h5>
                                <span style="font-size: 11px; background: rgba(16, 185, 129, 0.15); color: #34D399; padding: 3px 8px; border-radius: 12px; font-weight: 600; border: 1px solid rgba(52, 211, 153, 0.3);">
                                    Active Revision: {resp.get('revision', 1)}
                                </span>
                            </div>
                            
                            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px; font-size: 13px; color: #94A3B8; margin-bottom: 18px;">
                                <div>
                                    <strong style="color: #CBD5E1;">Producer ID:</strong> {resp.get('producer_id')}
                                </div>
                                <div>
                                    <strong style="color: #CBD5E1;">Filing Period:</strong> {resp.get('month')}
                                </div>
                                <div>
                                    <strong style="color: #CBD5E1;">Record UUID:</strong> <code style="font-size: 11px; color: #60A5FA;">{resp.get('record_id')}</code>
                                </div>
                                <div>
                                    <strong style="color: #CBD5E1;">Timestamp:</strong> {resp.get('submitted_at', '').replace('T', ' ')[:19]}
                                </div>
                            </div>
                            
                            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                                <thead>
                                    <tr style="border-bottom: 1.5px solid rgba(255, 255, 255, 0.1);">
                                        <th style="padding: 8px 10px; text-align: left; color: #94A3B8; font-weight: 500;">Plastic Type</th>
                                        <th style="padding: 8px 10px; text-align: right; color: #94A3B8; font-weight: 500;">Declared Weight</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {categories_rows}
                                    <tr style="border-top: 1.5px solid rgba(255, 255, 255, 0.15); font-weight: 700; font-size: 14px;">
                                        <td style="padding: 12px 10px 0 10px; color: #F1F5F9;">Total Obligation</td>
                                        <td style="padding: 12px 10px 0 10px; text-align: right; color: #60A5FA;">
                                            {resp.get('total_declared_kg', 0.0):,.1f} kg
                                        </td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                        """
                        st.markdown(receipt_html, unsafe_allow_html=True)
                    elif status == 409:
                        st.warning(f"⚠️ Ingestion Conflict: {resp.get('message', 'Record already exists.')}")
                    elif status == 422:
                        # Pydantic validation details
                        st.error(f"❌ Input Validation Error (422):")
                        st.json(resp.get("detail", {}))
                    else:
                        st.error(f"❌ Server Error ({status}): {resp.get('message', 'Unspecified execution failure.')}")
