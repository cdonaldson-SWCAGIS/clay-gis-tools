import streamlit as st
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add project root to path for imports (must be done first)
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Load environment variables from .env file
load_dotenv()

# App configuration
st.set_page_config(
    page_title="Clay AGOL Tools",
    page_icon=str(project_root / "static" / "icon.svg"),
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom CSS
def load_css(css_file):
    with open(css_file, "r") as f:
        css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# Apply custom CSS if file exists
css_path = os.path.join(project_root, ".streamlit", "style.css")
if os.path.exists(css_path):
    load_css(css_path)

# Import pages
from frontend.page_modules import authentication, webmap_filters, webmap_forms, webmap_analysis, settings
from backend.utils.logging import configure_logging

# Configure logging once at startup
configure_logging()

# Session state initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "gis" not in st.session_state:
    st.session_state.gis = None
if "debug_mode" not in st.session_state:
    # Read DEBUG_MODE from environment variable, default to True
    st.session_state.debug_mode = os.environ.get("DEBUG_MODE", "True").lower() == "true"

# If not authenticated, show authentication splash screen
if not st.session_state.authenticated:
    authentication.show()
else:
    # Sidebar navigation (only shown when authenticated)
    st.sidebar.title("Clay AGOL Tools")
    
    # Navigation
    page = st.sidebar.radio(
        "Navigation",
        ["Web Map Filters", "Web Map Forms", "Web Map Analysis", "Settings"],
        key="navigation"
    )
    
    # Page routing
    if page == "Web Map Filters":
        webmap_filters.show()
    elif page == "Web Map Forms":
        webmap_forms.show()
    elif page == "Web Map Analysis":
        webmap_analysis.show()
    elif page == "Settings":
        settings.show()
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.caption("Clay AGOL Tools v1.0.0")
