"""
frontend/components/policy_qa.py
=================================
EPR Compliance Policy Assistant with conversational interface and citations.
"""

import streamlit as st
from frontend.utils.api_client import APIClient

def render_policy_qa_tab(api_client: APIClient):
    """
    Renders the plain-English compliance policy RAG chatroom.
    """
    st.markdown("### **EPR Compliance Policy Assistant**")
    
    st.markdown(
        """
        <div class="glass-card">
            <h5 style="margin: 0 0 8px 0; color: #10B981;">Grounded Policy Compliance Intelligence</h5>
            <p style="margin: 0; font-size: 13px; color: #94A3B8; line-height: 1.5;">
                Ask plain-English questions regarding Extended Producer Responsibility (EPR) regulations or compliance SOPs. Answers are backed by context retrieved from ingested policy documents, preventing hallucinated summaries.
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # User question input
    user_q = st.text_input(
        "Enter compliance policy question:", 
        value="What is the variance threshold for flexible plastic?",
        help="Type any query relating to plastic compliance rules."
    )
    ask_btn = st.button("🔍 Query Policy Indexes")
    
    if ask_btn and user_q:
        with st.spinner("Reformulating query & searching ChromaDB vector index..."):
            status, resp = api_client.ask_policy_question(user_q)
            
            if status == 200:
                # Add to chat history in session_state
                st.session_state.chat_history.append((user_q, resp))
            else:
                st.error(f"Query execution failed ({status}): {resp.get('detail', 'Unspecified retrieval failure.')}")

    # Display chat room log entries
    if st.session_state.chat_history:
        st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)
        st.markdown("#### **Compliance Policy conversation history**")
        
        for q, ans in reversed(st.session_state.chat_history):
            # User bubble
            st.markdown(
                f"""
                <div style="background: rgba(255, 255, 255, 0.02); padding: 12px 18px; border-radius: 12px; border-left: 3px solid #64748B; margin-bottom: 8px;">
                    <span style="font-size: 10px; color: #64748B; font-weight: 600; display: block; letter-spacing: 0.05em; text-transform: uppercase;">Compliance Officer Query</span>
                    <p style="margin: 5px 0 0 0; font-size: 14px; font-weight: 600; color: #E2E8F0;">{q}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Assistant bubble
            is_fallback = ans.get("is_fallback", False)
            border_style = "border-left: 3px solid #EF4444 !important;" if is_fallback else "border-left: 3px solid #10B981 !important;"
            label_color = "#F87171" if is_fallback else "#34D399"
            
            st.markdown(
                f"""
                <div class="glass-card" style="{border_style} padding: 16px 20px;">
                    <span style="font-size: 10px; color: {label_color}; font-weight: 600; display: block; letter-spacing: 0.05em; text-transform: uppercase;">Verified Grounded Answer</span>
                    <p style="margin: 8px 0 0 0; font-size: 14px; line-height: 1.5; color: #F1F5F9;">{ans.get('answer')}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Render citations
            citations = ans.get("citations", [])
            if citations:
                with st.expander("📚 Ingested vector source citations"):
                    for idx, cit in enumerate(citations):
                        c1, c2, c3 = st.columns([2, 2, 1])
                        with c1:
                            st.markdown(f"**Doc {idx+1}:** `{cit.get('source')}`")
                        with c2:
                            st.markdown(f"**Section:** {cit.get('section')}")
                        with c3:
                            st.markdown(f"**Relevance:** `{cit.get('similarity_score'):.2f}`")
                            
                        st.markdown(
                            f"""
                            <div style="background: rgba(0, 0, 0, 0.25); padding: 10px 14px; border-radius: 8px; font-size: 13px; line-height: 1.5; color: #94A3B8; border: 1px solid rgba(255, 255, 255, 0.02); margin-bottom: 12px; font-family: 'Inter';">
                                "{cit.get('chunk_text')}"
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
            else:
                st.markdown(
                    "<p style='font-size: 12px; color: #64748B; font-style: italic; margin-left: 10px; margin-bottom: 20px;'>No citations retrieved (Fallback triggered).</p>", 
                    unsafe_allow_html=True
                )
            
            st.markdown("<hr style='border: 0; border-top: 1px solid rgba(255, 255, 255, 0.04); margin: 20px 0;'>", unsafe_allow_html=True)
            
    else:
        st.markdown(
            "<p style='font-size: 13px; color: #64748B; font-style: italic;'>Conversation log empty. Submit a query to search context index.</p>", 
            unsafe_allow_html=True
        )
