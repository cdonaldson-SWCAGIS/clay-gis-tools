import streamlit as st
import logging
import sys
import os
import platform

# Configure logging
logger = logging.getLogger("settings")

def show():
    """Display the Settings interface"""
    st.title("Settings")
    
    # General Settings
    st.subheader("General")
    
    # Debug mode
    debug_mode = st.checkbox(
        "Debug Mode",
        value=st.session_state.get("debug_mode", True),
        help="When enabled, operations will be simulated without making actual changes"
    )
    st.session_state.debug_mode = debug_mode
    
    # Logging level
    log_levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    
    current_level = "INFO"
    for level_name, level_value in log_levels.items():
        if logging.getLogger().level == level_value:
            current_level = level_name
            break
    
    log_level = st.selectbox(
        "Logging Level",
        list(log_levels.keys()),
        index=list(log_levels.keys()).index(current_level),
        help="Set the verbosity of logging messages"
    )
    logging.getLogger().setLevel(log_levels[log_level])
    
    # MAP_SUFFIX setting
    current_map_suffix = os.environ.get("MAP_SUFFIX", st.session_state.get("map_suffix", "_Copy"))
    map_suffix = st.text_input(
        "Map Suffix",
        value=current_map_suffix,
        help="Suffix appended to copied web map titles when using 'Save as New'",
        key="map_suffix_input"
    )
    st.session_state.map_suffix = map_suffix
    os.environ["MAP_SUFFIX"] = map_suffix
    
    st.divider()
    
    # Advanced Settings
    st.subheader("Advanced")
    
    # Request timeout
    request_timeout = st.number_input(
        "Request Timeout (seconds)",
        min_value=10,
        max_value=300,
        value=st.session_state.get("request_timeout", 60),
        help="Maximum time to wait for API requests"
    )
    st.session_state.request_timeout = request_timeout
    
    # Max items to return in searches
    max_items = st.number_input(
        "Max Search Results",
        min_value=10,
        max_value=1000,
        value=st.session_state.get("max_items", 25),
        help="Maximum number of items to return in search results"
    )
    st.session_state.max_items = max_items
    
    st.divider()
    
    # Session
    st.subheader("Session")
    if st.session_state.get("authenticated", False):
        st.write(f"Logged in as: **{st.session_state.get('username', 'Unknown')}**")
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.gis = None
            st.session_state.username = None
            st.session_state._env_auth_attempted = False
            st.rerun()
    else:
        st.write("Not logged in")
    
    st.divider()
    
    # System Information (collapsed)
    with st.expander("System Information"):
        python_version = sys.version.split()[0]
        st.write(f"**Python:** {python_version}")
        st.write(f"**Streamlit:** {st.__version__}")
        
        try:
            import arcgis
            st.write(f"**ArcGIS API:** {arcgis.__version__}")
        except (ImportError, AttributeError):
            st.write("**ArcGIS API:** Not available")
        
        st.write(f"**OS:** {platform.system()} {platform.release()}")
    
    st.divider()
    
    # Reset all settings
    if st.button("Reset All to Defaults"):
        st.session_state.debug_mode = True
        logging.getLogger().setLevel(logging.INFO)
        st.session_state.map_suffix = "_Copy"
        os.environ["MAP_SUFFIX"] = "_Copy"
        st.session_state.request_timeout = 60
        st.session_state.max_items = 25
        st.rerun()
