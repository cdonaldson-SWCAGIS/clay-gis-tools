import streamlit as st
import os
import sys

# Add the src directory to the Python path
sys.path.append(os.path.abspath("src"))

# App configuration
st.set_page_config(
    page_title="Clay AGOL Tools",
    page_icon="static/favicon.png",
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

# Create modules directory if it doesn't exist
os.makedirs("modules", exist_ok=True)

# Import modules (will be created in subsequent steps)
from modules import authentication, webmap_filters, webmap_forms, settings

# Sidebar navigation
st.sidebar.title("Clay AGOL Tools")
#st.sidebar.image("https://www.swca.com/images/made/images/uploads/SWCA_Logo_300_300_s_c1.png", width=200)

# Session state initialization
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "gis" not in st.session_state:
    st.session_state.gis = None
if "debug_mode" not in st.session_state:
    st.session_state.debug_mode = True

# Navigation
page = st.sidebar.radio(
    "Navigation",
    ["Authentication", "Web Map Filters", "Web Map Forms", "Settings"],
    key="navigation"
)

# Page routing
if page == "Authentication" or not st.session_state.authenticated:
    authentication.show()
elif page == "Web Map Filters":
    webmap_filters.show()
elif page == "Web Map Forms":
    webmap_forms.show()
elif page == "Settings":
    settings.show()

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("Clay AGOL Tools v1.0.0")

