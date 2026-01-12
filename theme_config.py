"""
Smart Retire AI - Theme Configuration

Modern Financial Theme with Dark Mode Support
"""

# Light Mode Theme (Modern Financial)
LIGHT_THEME = {
    # Primary Colors
    "primary": "#0066CC",        # Deep Blue - Main brand color
    "secondary": "#FFB020",      # Gold - Accent, highlights, CTAs
    "success": "#10B981",        # Emerald Green - Positive metrics
    "warning": "#F59E0B",        # Amber - Alerts
    "danger": "#EF4444",         # Red - Negative metrics

    # Background & Surface
    "background": "#F9FAFB",     # Light Gray
    "surface": "#FFFFFF",        # White - Cards
    "surface_alt": "#F3F4F6",   # Alternate surface

    # Text Colors
    "text_primary": "#1F2937",   # Dark Gray - Main text
    "text_secondary": "#6B7280", # Medium Gray - Secondary text
    "text_tertiary": "#9CA3AF",  # Light Gray - Tertiary text

    # Border & Divider
    "border": "#E5E7EB",         # Light border
    "divider": "#D1D5DB",        # Divider lines

    # Interactive Elements
    "hover": "#F3F4F6",          # Hover state
    "active": "#E5E7EB",         # Active state
    "focus": "#0066CC",          # Focus outline

    # Charts & Data Visualization
    "chart_blue": "#0066CC",
    "chart_green": "#10B981",
    "chart_gold": "#FFB020",
    "chart_purple": "#8B5CF6",
    "chart_teal": "#14B8A6",
    "chart_orange": "#F97316",
}

# Dark Mode Theme
DARK_THEME = {
    # Primary Colors (adjusted for dark background)
    "primary": "#3B82F6",        # Bright Blue
    "secondary": "#FCD34D",      # Light Gold
    "success": "#34D399",        # Brighter Emerald
    "warning": "#FBBF24",        # Bright Amber
    "danger": "#F87171",         # Bright Red

    # Background & Surface
    "background": "#0F172A",     # Dark Slate
    "surface": "#1E293B",        # Slate Gray - Cards
    "surface_alt": "#334155",    # Lighter slate

    # Text Colors
    "text_primary": "#F1F5F9",   # Light Gray - Main text
    "text_secondary": "#CBD5E1",  # Medium Light - Secondary text
    "text_tertiary": "#94A3B8",  # Medium - Tertiary text

    # Border & Divider
    "border": "#334155",         # Dark border
    "divider": "#475569",        # Dark divider

    # Interactive Elements
    "hover": "#334155",          # Hover state
    "active": "#475569",         # Active state
    "focus": "#3B82F6",          # Focus outline

    # Charts & Data Visualization
    "chart_blue": "#60A5FA",
    "chart_green": "#34D399",
    "chart_gold": "#FCD34D",
    "chart_purple": "#A78BFA",
    "chart_teal": "#2DD4BF",
    "chart_orange": "#FB923C",
}


def get_theme_css(theme_colors: dict) -> str:
    """Generate CSS for the theme."""
    return f"""
    <style>
    /* CSS Variables for Theme */
    :root {{
        --primary-color: {theme_colors['primary']};
        --secondary-color: {theme_colors['secondary']};
        --success-color: {theme_colors['success']};
        --warning-color: {theme_colors['warning']};
        --danger-color: {theme_colors['danger']};
        --background-color: {theme_colors['background']};
        --surface-color: {theme_colors['surface']};
        --text-primary: {theme_colors['text_primary']};
        --text-secondary: {theme_colors['text_secondary']};
        --border-color: {theme_colors['border']};
    }}

    /* Global Styles */
    .stApp {{
        background-color: {theme_colors['background']};
        color: {theme_colors['text_primary']};
    }}

    /* Headers */
    h1, h2, h3, h4, h5, h6 {{
        color: {theme_colors['text_primary']} !important;
    }}

    /* Primary Buttons */
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {theme_colors['primary']} 0%, {theme_colors['secondary']} 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1) !important;
        transition: all 0.3s ease !important;
    }}

    .stButton > button[kind="primary"]:hover {{
        transform: translateY(-2px) !important;
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2) !important;
    }}

    /* Secondary Buttons */
    .stButton > button {{
        background-color: {theme_colors['surface']} !important;
        color: {theme_colors['primary']} !important;
        border: 2px solid {theme_colors['border']} !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }}

    .stButton > button:hover {{
        border-color: {theme_colors['primary']} !important;
        background-color: {theme_colors['hover']} !important;
    }}

    /* Cards & Expanders */
    .stExpander {{
        background-color: {theme_colors['surface']} !important;
        border: 1px solid {theme_colors['border']} !important;
        border-radius: 8px !important;
    }}

    /* Metrics */
    [data-testid="stMetricValue"] {{
        color: {theme_colors['primary']} !important;
        font-weight: 700 !important;
    }}

    [data-testid="stMetricDelta"] {{
        font-weight: 600 !important;
    }}

    /* Success Metric */
    [data-testid="stMetricDelta"][data-test-delta-type="positive"] {{
        color: {theme_colors['success']} !important;
    }}

    /* Negative Metric */
    [data-testid="stMetricDelta"][data-test-delta-type="negative"] {{
        color: {theme_colors['danger']} !important;
    }}

    /* Input Fields */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > div {{
        background-color: {theme_colors['surface']} !important;
        color: {theme_colors['text_primary']} !important;
        border: 1px solid {theme_colors['border']} !important;
        border-radius: 6px !important;
    }}

    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {{
        border-color: {theme_colors['primary']} !important;
        box-shadow: 0 0 0 1px {theme_colors['primary']} !important;
    }}

    /* Progress Bar */
    .stProgress > div > div > div {{
        background: linear-gradient(90deg, {theme_colors['primary']} 0%, {theme_colors['secondary']} 100%) !important;
    }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}

    .stTabs [data-baseweb="tab"] {{
        background-color: {theme_colors['surface']} !important;
        color: {theme_colors['text_secondary']} !important;
        border-radius: 6px 6px 0 0 !important;
        border: 1px solid {theme_colors['border']} !important;
        border-bottom: none !important;
        font-weight: 500 !important;
    }}

    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        background-color: {theme_colors['primary']} !important;
        color: white !important;
        border-color: {theme_colors['primary']} !important;
    }}

    /* Success Messages */
    .stSuccess {{
        background-color: rgba(16, 185, 129, 0.1) !important;
        color: {theme_colors['success']} !important;
        border-left: 4px solid {theme_colors['success']} !important;
    }}

    /* Info Messages */
    .stInfo {{
        background-color: rgba(0, 102, 204, 0.1) !important;
        color: {theme_colors['primary']} !important;
        border-left: 4px solid {theme_colors['primary']} !important;
    }}

    /* Warning Messages */
    .stWarning {{
        background-color: rgba(245, 158, 11, 0.1) !important;
        color: {theme_colors['warning']} !important;
        border-left: 4px solid {theme_colors['warning']} !important;
    }}

    /* Error Messages */
    .stError {{
        background-color: rgba(239, 68, 68, 0.1) !important;
        color: {theme_colors['danger']} !important;
        border-left: 4px solid {theme_colors['danger']} !important;
    }}

    /* DataFrames */
    .stDataFrame {{
        border: 1px solid {theme_colors['border']} !important;
        border-radius: 8px !important;
    }}

    /* Sidebar */
    [data-testid="stSidebar"] {{
        background-color: {theme_colors['surface']} !important;
        border-right: 1px solid {theme_colors['border']} !important;
    }}

    /* Links */
    a {{
        color: {theme_colors['primary']} !important;
        text-decoration: none !important;
        font-weight: 500 !important;
    }}

    a:hover {{
        color: {theme_colors['secondary']} !important;
        text-decoration: underline !important;
    }}

    /* Radio Buttons */
    .stRadio > div {{
        background-color: {theme_colors['surface']} !important;
        padding: 12px !important;
        border-radius: 8px !important;
        border: 1px solid {theme_colors['border']} !important;
    }}

    /* Checkboxes */
    .stCheckbox > label > div[data-testid="stMarkdownContainer"] > p {{
        color: {theme_colors['text_primary']} !important;
    }}

    /* Sliders */
    .stSlider > div > div > div {{
        background-color: {theme_colors['border']} !important;
    }}

    .stSlider > div > div > div > div {{
        background-color: {theme_colors['primary']} !important;
    }}

    /* File Uploader */
    [data-testid="stFileUploader"] {{
        background-color: {theme_colors['surface']} !important;
        border: 2px dashed {theme_colors['border']} !important;
        border-radius: 8px !important;
    }}

    /* Download Button */
    .stDownloadButton > button {{
        background: linear-gradient(135deg, {theme_colors['success']} 0%, {theme_colors['primary']} 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
    }}

    /* Spinner */
    .stSpinner > div {{
        border-top-color: {theme_colors['primary']} !important;
    }}

    /* Code Blocks */
    code {{
        background-color: {theme_colors['surface_alt']} !important;
        color: {theme_colors['text_primary']} !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-family: 'Monaco', 'Menlo', monospace !important;
    }}

    /* Markdown */
    .stMarkdown {{
        color: {theme_colors['text_primary']} !important;
    }}

    /* Divider */
    hr {{
        border-color: {theme_colors['divider']} !important;
        opacity: 0.3 !important;
    }}
    </style>
    """


def get_theme_toggle_html() -> str:
    """Generate HTML for theme toggle button."""
    return """
    <div style="position: fixed; top: 10px; right: 10px; z-index: 999999;">
        <button id="theme-toggle" style="
            background: linear-gradient(135deg, #0066CC 0%, #FFB020 100%);
            color: white;
            border: none;
            padding: 10px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-weight: 600;
            font-size: 14px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 6px;
        " onmouseover="this.style.transform='scale(1.05)'"
           onmouseout="this.style.transform='scale(1)'">
            <span id="theme-icon">🌙</span>
            <span id="theme-text">Dark Mode</span>
        </button>
    </div>
    """
