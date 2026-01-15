import streamlit as st
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# App configuration
st.set_page_config(
    page_title="Clay AGOL Tools",
    page_icon="../static/icon.svg",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load custom CSS
def load_css(css_file):
    with open(css_file, "r") as f:
        css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

# Apply custom CSS if file exists
css_path = os.path.join(".streamlit", "style.css")
if os.path.exists(css_path):
    load_css(css_path)

# Import pages
from frontend.pages import authentication, webmap_filters, webmap_forms, webmap_analysis, settings
from backend.utils.logging import configure_logging

# Configure logging once at startup
configure_logging()

# Sidebar navigation
st.sidebar.title("Clay AGOL Tools")
#st.sidebar.image("https://www.swca.com/images/made/images/uploads/SWCA_Logo_300_300_s_c1.png", width=200)

# Session state initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "gis" not in st.session_state:
    st.session_state.gis = None
if "debug_mode" not in st.session_state:
    # Read DEBUG_MODE from environment variable, default to True
    st.session_state.debug_mode = os.environ.get("DEBUG_MODE", "True").lower() == "true"

# Attempt authentication from environment variables if not already authenticated
if not st.session_state.authenticated:
    try:
        gis_from_env = authentication.authenticate_from_env()
        st.session_state.gis = gis_from_env
        st.session_state.authenticated = True
        st.session_state.username = gis_from_env.properties.user.username
        st.success(f"Automatically connected as {gis_from_env.properties.user.username} via environment variables.")
    except (ValueError, Exception) as e:
        st.warning(f"Automatic authentication failed: {e}. Please use the 'Authentication' page to connect manually.")
        st.session_state.authenticated = False # Ensure it's false if auto-auth fails

# Navigation
page = st.sidebar.radio(
    "Navigation",
    ["Authentication", "Web Map Filters", "Web Map Forms", "Web Map Analysis", "Clip by Template Tag", "Settings"],
    key="navigation"
)

# Page routing
if page == "Authentication" or not st.session_state.authenticated:
    authentication.show() # Show authentication page if not authenticated or explicitly selected
elif page == "Web Map Filters":
    webmap_filters.show()
elif page == "Web Map Forms":
    webmap_forms.show()
elif page == "Web Map Analysis":
    webmap_analysis.show()
elif page == "Clip by Template Tag":
    from frontend.pages.clip_by_template import show
    show()
elif page == "Settings":
    settings.show()

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("Clay AGOL Tools v1.0.0")
