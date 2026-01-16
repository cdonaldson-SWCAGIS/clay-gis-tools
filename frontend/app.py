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

# Import authentication module (lightweight, needed for splash screen)
# Other page modules are lazy-loaded when needed to reduce startup time
from frontend.page_modules import authentication
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
    st.sidebar.subheader("Webmap Tools")
    page = st.sidebar.radio(
        "Webmap Tools",
        ["Update Layer Filters", "Update Layer Form Default Values", "Bulk Create Collections", "Settings"],
        key="navigation",
        label_visibility="collapsed"
    )
    
    # Debug mode indicator
    if st.session_state.get("debug_mode", True):
        st.sidebar.warning("Debug mode ON - changes simulated")
    
    # Page routing with lazy imports to reduce initial load time
    if page == "Update Layer Filters":
        from frontend.page_modules import webmap_filters
        webmap_filters.show()
    elif page == "Update Layer Form Default Values":
        from frontend.page_modules import webmap_forms
        webmap_forms.show()
    elif page == "Bulk Create Collections":
        from frontend.page_modules import bulk_collections
        bulk_collections.show()
    elif page == "Settings":
        from frontend.page_modules import settings
        settings.show()
    
    # Footer
    st.sidebar.markdown("---")
    st.sidebar.caption("Clay AGOL Tools v1.0.0")
