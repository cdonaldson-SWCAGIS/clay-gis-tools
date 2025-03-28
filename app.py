import streamlit as st
import os
import sys

# Add the src directory to the Python path
sys.path.append(os.path.abspath("src"))

# App configuration
st.set_page_config(
    page_title="SWCA GIS Tools",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create modules directory if it doesn't exist
os.makedirs("modules", exist_ok=True)

# Import modules (will be created in subsequent steps)
from modules import authentication, webmap_filters, webmap_forms, settings

# Sidebar navigation
st.sidebar.title("SWCA GIS Tools")
st.sidebar.image("https://www.swca.com/images/made/images/uploads/SWCA_Logo_300_300_s_c1.png", width=200)

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
st.sidebar.caption("SWCA GIS Tools v1.0.0")
st.sidebar.caption("© 2025 SWCA Environmental Consultants")
