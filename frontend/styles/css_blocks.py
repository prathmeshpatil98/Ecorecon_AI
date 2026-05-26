"""
frontend/styles/css_blocks.py
==============================
Central styling, fonts, and vector branding components for the modular Streamlit frontend.
"""

# Premium Custom CSS Injection overrides
GLOBAL_CSS = """
<style>
    /* 1. Import Display & Body Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=Inter:wght@300;400;500;600&display=swap');

    /* 2. Global Fonts Setting */
    html, body, [data-testid="stAppViewContainer"] {
        font-family: 'Inter', sans-serif !important;
        background-color: #0B0F19 !important;
        color: #F8FAFC !important;
    }

    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em !important;
        color: #F8FAFC !important;
    }

    /* 3. Hide Default Streamlit Margins & Header/Footer */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    div.block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }

    /* 4. Glassmorphism Design System Card Classes */
    .glass-card {
        border-radius: 16px;
        background: rgba(17, 24, 39, 0.7);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.04);
        box-shadow: 0 10px 40px 0 rgba(0, 0, 0, 0.5);
        padding: 24px;
        margin-bottom: 24px;
    }

    .active-glow {
        border: 1px solid rgba(16, 185, 129, 0.25) !important;
        box-shadow: 0 0 25px rgba(16, 185, 129, 0.06) !important;
    }

    /* 5. Custom Table Styling */
    .matrix-table {
        width: 100%;
        border-collapse: collapse;
        margin: 16px 0;
        font-size: 14px;
        text-align: left;
    }
    
    .matrix-table th {
        background-color: #111827;
        color: #10B981;
        padding: 14px 16px;
        font-family: 'Outfit', sans-serif;
        font-weight: 600;
        border-bottom: 2px solid rgba(255, 255, 255, 0.05);
    }
    
    .matrix-table td {
        padding: 14px 16px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.02);
        color: #E2E8F0;
    }

    .matrix-table tr:hover {
        background-color: rgba(255, 255, 255, 0.015);
    }

    /* 6. Dynamic Colored Metrics tags */
    .tag {
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 600;
        display: inline-block;
        letter-spacing: 0.05em;
        text-align: center;
    }
    
    .tag-none {
        background: rgba(16, 185, 129, 0.12);
        color: #34D399;
        border: 1px solid rgba(16, 185, 129, 0.2);
    }
    
    .tag-low {
        background: rgba(245, 158, 11, 0.12);
        color: #FBBF24;
        border: 1px solid rgba(245, 158, 11, 0.2);
    }
    
    .tag-moderate {
        background: rgba(249, 115, 22, 0.12);
        color: #FB923C;
        border: 1px solid rgba(249, 115, 22, 0.2);
    }
    
    .tag-high {
        background: rgba(239, 68, 68, 0.12);
        color: #F87171;
        border: 1px solid rgba(239, 68, 68, 0.2);
    }
    
    .tag-missing {
        background: rgba(107, 114, 128, 0.12);
        color: #9CA3AF;
        border: 1px solid rgba(107, 114, 128, 0.2);
    }

    /* 7. Metric Card enhancements */
    div[data-testid="stMetricValue"] {
        font-family: 'Outfit', sans-serif !important;
        font-weight: 700 !important;
        color: #10B981 !important;
        font-size: 28px !important;
    }
    
    div[data-testid="stMetricLabel"] {
        font-family: 'Inter', sans-serif !important;
        color: #94A3B8 !important;
        font-weight: 500 !important;
        font-size: 13px !important;
        letter-spacing: 0.02em !important;
    }
</style>
"""

# Clean corporate vector SVG Branding Logo
SVG_BRANDING_BADGE = """
<div style="display: flex; align-items: center; gap: 14px; margin-bottom: 25px; padding: 5px;">
    <svg width="40" height="40" viewBox="0 0 100 100" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="100" height="100" rx="24" fill="#111827" />
        <path d="M50 20L80 70H20L50 20Z" fill="url(#paint0_linear)" />
        <circle cx="50" cy="55" r="12" fill="#0B0F19" />
        <circle cx="50" cy="55" r="6" fill="#34D399" />
        <defs>
            <linearGradient id="paint0_linear" x1="50" y1="20" x2="50" y2="70" gradientUnits="userSpaceOnUse">
                <stop stop-color="#10B981" />
                <stop offset="1" stop-color="#34D399" />
            </linearGradient>
        </defs>
    </svg>
    <div>
        <h3 style="margin: 0; font-size: 18px; font-weight: 700; font-family: 'Outfit'; color: #F8FAFC; letter-spacing: -0.01em;">
            EcoRecon AI
        </h3>
        <span style="font-size: 10px; font-weight: 500; font-family: 'Inter'; color: #10B981; text-transform: uppercase; letter-spacing: 0.08em; display: block; margin-top: 1px;">
            EPR Audit Platform
        </span>
    </div>
</div>
"""
