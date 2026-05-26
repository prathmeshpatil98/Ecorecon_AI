"""
frontend/components/audit.py
=============================
Reconciliation dashboard rendering comparison tables, severity tags, and Groq narratives.
"""

import streamlit as st
from frontend.utils.api_client import APIClient

def render_audit_tab(api_client: APIClient):
    """
    Renders the deterministic reconciliation comparison matrix and 
    associated Groq LLM synthesized narrative.
    """
    st.markdown("### **Reconciliation & Audit Control Room**")
    
    st.markdown(
        """
        <div class="glass-card">
            <h5 style="margin: 0 0 8px 0; color: #10B981;">Reconciliation Execution & Audit Trails</h5>
            <p style="margin: 0; font-size: 13px; color: #94A3B8; line-height: 1.5;">
                Compares submitted declarations against actual ERP procurement records. Discrepancies exceeding the regulatory <b>±5% obligation limit</b> are flagged automatically with computed severity tiers.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Audit selection triggers
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        producer_id = st.text_input("Obligation Producer ID", value=st.session_state.active_producer).strip().upper()
        
    available_months = ["2026-01", "2026-02", "2026-03", "2026-04", "2026-05"]
    default_month = st.session_state.active_month
    if default_month in available_months:
        default_index = available_months.index(default_month)
    else:
        default_index = 3  # Default to 2026-04
        
    with col2:
        month = st.selectbox("Obligation Target Month", available_months, index=default_index)
    with col3:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        trigger_audit = st.button("⚖️ Run Reconciliation", use_container_width=True)
        
    if trigger_audit:
        with st.spinner("Invoking LangGraph DAG workflow and Groq Narrative engine..."):
            status, data = api_client.get_reconciliation_summary(producer_id, month)
            
            if status == 200:
                st.success("✓ Reconciliation Audit complete!")
                
                recon = data.get("reconciliation", {})
                
                # Visual KPIs rows
                k1, k2, k3 = st.columns(3)
                with k1:
                    is_mismatched = recon.get("has_mismatch")
                    status_styled = "🔴 MISMATCHED" if is_mismatched else "🟢 CLEAN"
                    st.metric(label="Overall Obligation Status", value=status_style_custom(is_mismatched))
                with k2:
                    st.metric(label="Total Obligation Variance", value=f"{recon.get('total_variance_kg'):,.2f} kg")
                with k3:
                    st.metric(label="Overall Deviation %", value=f"{recon.get('overall_deviation_pct'):.2f} %")
                    
                st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
                st.markdown("#### **Reconciliation Audit comparison Matrix**")
                
                table_html = (
                    '<table class="matrix-table">\n'
                    '    <thead>\n'
                    '        <tr>\n'
                    '            <th>Plastic Category</th>\n'
                    '            <th>Declared Weight (kg)</th>\n'
                    '            <th>ERP Procured (kg)</th>\n'
                    '            <th>Variance (kg)</th>\n'
                    '            <th>Deviation %</th>\n'
                    '            <th>Obligation Flag</th>\n'
                    '            <th>Severity Tier</th>\n'
                    '        </tr>\n'
                    '    </thead>\n'
                    '    <tbody>\n'
                )
                
                for cat in recon.get("categories", []):
                    var_val = cat.get("variance_kg")
                    var_styled = f"+{var_val:,.2f}" if var_val > 0 else f"{var_val:,.2f}"
                    # Flag color settings (red vs green)
                    var_color = "#F87171" if cat.get("is_flagged") else "#34D399"
                    
                    flag_styled = "🚩 Mismatch" if cat.get("is_flagged") else "✓ Matches"
                    
                    severity = cat.get("severity")
                    sev_class = f"tag tag-{severity.lower()}"
                    
                    table_html += (
                        '        <tr>\n'
                        f'            <td style="font-weight: 600;">{cat.get("category").replace("_", " ").title()}</td>\n'
                        f'            <td>{cat.get("declared_kg"):,.2f}</td>\n'
                        f'            <td>{cat.get("procured_kg"):,.2f}</td>\n'
                        f'            <td style="color: {var_color}; font-weight: 600;">{var_styled}</td>\n'
                        f'            <td>{cat.get("deviation_pct"):.2f}%</td>\n'
                        f'            <td style="color: {var_color}; font-weight: 600;">{flag_styled}</td>\n'
                        f'            <td><span class="{sev_class}">{severity.upper()}</span></td>\n'
                        '        </tr>\n'
                    )
                    
                table_html += "    </tbody>\n</table>"
                st.markdown(table_html, unsafe_allow_html=True)
                
                # Render Groq generated narrative card
                st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
                st.markdown("#### **🤖 Groq compliance Narrative**")
                st.markdown(
                    f"""
                    <div class="glass-card active-glow" style="border-left: 4px solid #10B981 !important; font-size: 14px; line-height: 1.6; color: #E2E8F0; font-style: italic;">
                        "{data.get('narrative')}"
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
                # Render engine audit metadata
                st.markdown(
                    f"<p style='font-size:11px; color:#64748B; margin-top: -10px;'>Audit Log ID: {data.get('log_id')} | Engine duration: {recon.get('execution_ms')}ms | Source record count: {recon.get('erp_record_count')}</p>",
                    unsafe_allow_html=True
                )
                
            else:
                st.error(f"Reconciliation failed ({status}): {data.get('message', 'Unspecified execution failure.')}")

def status_style_custom(is_mismatched: bool) -> str:
    """Helper to convert status flags into visual highlights."""
    return "MISMATCHED" if is_mismatched else "CLEAN"
