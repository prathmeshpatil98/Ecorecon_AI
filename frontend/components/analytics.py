"""
frontend/components/analytics.py
=================================
Operational compliance metrics and visual analytics share charts.
"""

import streamlit as st
import pandas as pd

def render_analytics_tab():
    """
    Renders real-time plastic packaging analytics and compliance status figures.
    """
    st.markdown("### **Operational Compliance Health**")
    st.markdown(
        """
        <p style="font-size: 14px; color: #94A3B8; margin-bottom: 20px;">
            Overview of overall Extended Producer Responsibility (EPR) obligations, active DB statistics, and audit metrics.
        </p>
        """,
        unsafe_allow_html=True
    )

    # Metrics Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric(label="Ingested Submissions", value="4 Months", delta="Active Period")
    with m2:
        st.metric(label="Reconciled Obligations", value="3 Months", delta="Verified OK")
    with m3:
        st.metric(label="Identified Deviations (>5%)", value="1 Month", delta="Audit Warning", delta_color="inverse")
    with m4:
        st.metric(label="Active Regulatory Context Chunks", value="62 Chunks", delta="ChromaDB Index")

    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
    st.markdown("---")
    st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

    # Simulator charts
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("#### **Historical Plastic packaging declared vs. procured (FY 2026)**")
        st.markdown(
            "<p style='font-size: 13px; color: #64748B;'>Audit comparisons showing month-over-month obligations vs ERP feeds.</p>",
            unsafe_allow_html=True
        )
        
        # Historical simulation data
        data = {
            "Month": ["2026-01", "2026-02", "2026-03", "2026-04"],
            "Rigid Declared": [11500, 12200, 11800, 1000],
            "Rigid Procured": [11300, 12050, 11950, 11800],
            "Flexible Declared": [8000, 8800, 9200, 500],
            "Flexible Procured": [8150, 8900, 9100, 9100]
        }
        df = pd.DataFrame(data)
        st.line_chart(df.set_index("Month"), use_container_width=True)

    with col2:
        st.markdown("#### **Packaging Category Weights**")
        st.markdown(
            "<p style='font-size: 13px; color: #64748B;'>Weight distribution shares across active categories.</p>",
            unsafe_allow_html=True
        )
        category_data = pd.DataFrame({
            "Plastic Type": ["Rigid Plastic", "Flexible Plastic", "Multilayer Plastic"],
            "Weight Share (%)": [55.2, 33.8, 11.0]
        })
        st.bar_chart(category_data.set_index("Plastic Type"), use_container_width=True)
