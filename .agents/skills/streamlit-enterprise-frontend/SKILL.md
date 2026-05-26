---
name: streamlit-enterprise-frontend
description: |
  Use this skill to implement state-of-the-art, premium dark-theme Streamlit interfaces. Specializes in custom CSS injections, glassmorphism, responsive data metrics, and async FastAPI client integrations.
---

# Streamlit Enterprise Frontend Skill

## 1. Design Philosophy & Visual Aesthetics

Standard, out-of-the-box Streamlit apps look basic, generic, and unpolished. For enterprise-grade platforms, the frontend must deliver a premium, modern, and high-fidelity interface.

```
   ┌────────────────────────────────────────────────────────┐
   │             HSL-TAILORED DARK COLOR PALETTE            │
   ├───────────────────┬────────────────────────────────────┤
   │ Slate Base        │ #0B0F19 (Deep Navy/Black Slate)    │
   │ Card Background   │ #171E30 (Slate Navy Card Base)     │
   │ Accent Green      │ #10B981 (Vibrant Brand Emerald)    │
   │ Accent Green Hover│ #34D399 (Light Emerald Green)      │
   │ Alert Red         │ #EF4444 (Crimson Mismatch Alert)   │
   │ Text Primary      │ #F8FAFC (Ultra White / Light Slate)│
   └───────────────────┴────────────────────────────────────┘
```

---

## 2. Global Custom CSS Injection Specifications

Every page run must inject a global layout configuration using `st.markdown(..., unsafe_allow_html=True)` to override Streamlit's default margins, fonts, and controls.

### Premium Styling Template

```html
<style>
    /* 1. Import Premium Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Inter:wght@300;400;600&display=swap');

    /* 2. Base App Customizations */
    .stApp {
        background-color: #0B0F19;
        font-family: 'Inter', sans-serif;
        color: #F8FAFC;
    }
    
    /* 3. Header Outfit Font Styling */
    h1, h2, h3 {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
    }
    
    /* 4. Hide Streamlit Footer & Top Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* 5. Glassmorphism Container Card class */
    .glass-card {
        border-radius: 16px;
        background: rgba(23, 30, 48, 0.6);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.05);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.4);
        padding: 24px;
        margin-bottom: 20px;
    }
    
    /* 6. Glowing emerald borders for active sections */
    .active-card {
        border: 1px solid rgba(16, 185, 129, 0.3) !important;
        box-shadow: 0 0 15px rgba(16, 185, 129, 0.1) !important;
    }
</style>
```

---

## 3. API Integration & Async Resilience

Streamlit runs synchronously from top to bottom. To connect with the FastAPI backend cleanly:
1.  **Shared HTTP Session**: Instantiate an `httpx.Client(base_url="http://localhost:8000")` to persist connections.
2.  **Graceful Degradation**: Wrap all backend queries inside try/except blocks to alert users of database locks or network timeouts.
3.  **FastAPI Error Parsing**: Extract detail blocks on `422 Unprocessable Entity` or `409 Conflict` to render detailed alert banners.

---

## 4. UI Tab Component Blueprints

The interface is structured into four interactive workspaces utilizing standard `st.tabs`:

```
   ┌───────────────────────────────────────────────────────────────────────┐
   │ 1. Analytics Hub    │ 2. Submit Ingestion │ 3. Audit Room │ 4. Policy │
   └───────────────────────────────────────────────────────────────────────┘
```

---

### A. Tab 1: Analytics Hub
*   **Purpose**: Real-time snapshot of the GreenPack compliance state.
*   **Components**:
    *   Dynamic metrics cards (Total Declarations, Unreconciled Months, Active Flagged Discrepancies).
    *   Stateful dynamic charts (using `plotly` or `streamlit` native line/bar charts) representing historical plastic packaging metrics.

### B. Tab 2: Monthly Declaration Ingestion
*   **Purpose**: Streamlined monthly data entry form for compliance officers.
*   **Components**:
    *   **Month Selector**: Input format enforcing `YYYY-MM`.
    *   **Form Container**: Custom number inputs for Rigid, Flexible, and Multilayer categories with boundary limits ($0.0$ to $10,000,000.0$ kg).
    *   **Deterministic Validation Feedback**: Dynamic calculations of total weight on-the-fly.

### C. Tab 3: Reconciliation & Audit Dashboard
*   **Purpose**: The central control room. Fetches declarations, triggers the LangGraph backend, and parses calculations.
*   **Components**:
    *   **Selection Selectbox**: Dynamically populated list of existing monthly submissions.
    *   **Side-by-Side Comparison Matrix**: Custom styled table showing:
        *   Declared kg vs. Procured kg.
        *   Calculated Variance (kg) with green/red positive/negative indicators.
        *   Deviation % showing severity flags.
    *   **Groq narrative card**: Glassmorphic text block presenting the synthesized 3-5 sentence audit narrative.

### D. Tab 4: Compliance Policy Intelligence (RAG)
*   **Purpose**: Plain-English regulatory assistant.
*   **Components**:
    *   **Chat Input**: Clean dialog bar for compliance questions.
    *   **Answer panel**: Grounded responses rendered cleanly.
    *   **Citation Expander**: Collapsible panels displaying:
        *   Source document name.
        *   Specific section header.
        *   Cosine similarity matching score with visual meter indicators.
