import streamlit as st
import logging
import sys
import os
from typing import Dict, Any

# Configure logging
logger = logging.getLogger("settings")

def show():
    """Display the Settings interface"""
    st.title("Settings")
    
    # Display information about settings
    st.markdown("""
    ## Application Settings
    
    Configure global settings for the Clay GIS Tools application.
    These settings will be applied across all tools.
    """)
    
    # Create tabs for different settings categories
    tab1, tab2 = st.tabs(["General", "Advanced"])
    
    with tab1:
        show_general_settings()
    
    with tab2:
        show_advanced_settings()
    
    # Show help information
    show_help()

def show_general_settings():
    """Display general settings"""
    st.header("General Settings")
    
    # Debug mode
    debug_mode = st.checkbox(
        "Debug Mode (Global)",
        value=st.session_state.get("debug_mode", True),
        help="When enabled, operations will be simulated without making actual changes"
    )
    
    # Store in session state
    if debug_mode != st.session_state.get("debug_mode"):
        st.session_state.debug_mode = debug_mode
        st.success("Debug mode updated")
    
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
    
    # Apply logging level
    if log_level != current_level:
        numeric_level = log_levels[log_level]
        logging.getLogger().setLevel(numeric_level)
        st.success(f"Logging level set to {log_level}")
    
    # MAP_SUFFIX setting
    st.subheader("Web Map Settings")
    
    # Get current MAP_SUFFIX from environment or session state
    current_map_suffix = os.environ.get("MAP_SUFFIX", st.session_state.get("map_suffix", "_Copy"))
    
    map_suffix = st.text_input(
        "Map Suffix (for Save as New)",
        value=current_map_suffix,
        help="Suffix to append to copied web map titles (e.g., '_Copy', '_Draft'). Used when saving web maps as new.",
        key="map_suffix_input"
    )
    
    # Store in session state and update environment variable for this session
    if map_suffix != st.session_state.get("map_suffix"):
        st.session_state.map_suffix = map_suffix
        os.environ["MAP_SUFFIX"] = map_suffix
        st.success(f"Map suffix set to '{map_suffix}'")
    
    # UI theme
    st.subheader("UI Theme")
    
    # Theme selection
    theme = st.radio(
        "Select Theme",
        ["Light", "Dark"],
        horizontal=True,
        help="Choose the application theme"
    )
    
    if theme == "Dark":
        st.info("Dark theme is applied through your Streamlit settings. You can change it by clicking on the menu in the top right corner and selecting 'Settings'.")
    
    # Logout button
    st.subheader("Session")
    if st.session_state.get("authenticated", False):
        st.write(f"Logged in as: **{st.session_state.get('username', 'Unknown')}**")
        if st.button("Logout", key="logout_button"):
            st.session_state.authenticated = False
            st.session_state.gis = None
            st.session_state.username = None
            st.session_state._env_auth_attempted = False
            st.rerun()
    
    # Reset settings
    if st.button("Reset to Defaults", key="reset_general"):
        st.session_state.debug_mode = True
        logging.getLogger().setLevel(logging.INFO)
        st.session_state.map_suffix = "_Copy"
        os.environ["MAP_SUFFIX"] = "_Copy"
        st.success("General settings reset to defaults")
        st.rerun()

def show_advanced_settings():
    """Display advanced settings"""
    st.header("Advanced Settings")
    
    # Request timeout
    request_timeout = st.number_input(
        "Request Timeout (seconds)",
        min_value=10,
        max_value=300,
        value=st.session_state.get("request_timeout", 60),
        help="Maximum time to wait for API requests to complete"
    )
    
    if request_timeout != st.session_state.get("request_timeout"):
        st.session_state.request_timeout = request_timeout
        st.success(f"Request timeout set to {request_timeout} seconds")
    
    # Max items to return in searches
    max_items = st.number_input(
        "Max Search Results",
        min_value=10,
        max_value=1000,
        value=st.session_state.get("max_items", 25),
        help="Maximum number of items to return in search results"
    )
    
    if max_items != st.session_state.get("max_items"):
        st.session_state.max_items = max_items
        st.success(f"Max search results set to {max_items}")
    
    # System information
    st.subheader("System Information")
    
    # Python version
    python_version = sys.version.split()[0]
    st.write(f"- **Python Version**: {python_version}")
    
    # Streamlit version
    import streamlit as st_version
    st.write(f"- **Streamlit Version**: {st_version.__version__}")
    
    # ArcGIS API version
    try:
        import arcgis
        st.write(f"- **ArcGIS API Version**: {arcgis.__version__}")
    except (ImportError, AttributeError):
        st.write("- **ArcGIS API Version**: Not available")
    
    # Operating system
    import platform
    st.write(f"- **Operating System**: {platform.system()} {platform.release()}")
    
    # Reset settings
    if st.button("Reset to Defaults", key="reset_advanced"):
        st.session_state.request_timeout = 60
        st.session_state.max_items = 25
        st.success("Advanced settings reset to defaults")
        st.rerun()

def show_help():
    """Display help information for the Settings page"""
    with st.expander("Need Help?"):
        st.markdown("""
        ### Settings Help
        
        #### General Settings
        - **Debug Mode**: When enabled, operations will be simulated without making actual changes to the server
        - **Logging Level**: Controls the verbosity of logging messages
          - DEBUG: Most verbose, shows all messages
          - INFO: Shows informational messages and above
          - WARNING: Shows warnings and above
          - ERROR: Shows errors and above
          - CRITICAL: Shows only critical errors
        - **Map Suffix**: Suffix to append to copied web map titles when using "Save as New" feature (default: "_Copy")
        
        #### Advanced Settings
        - **Request Timeout**: Maximum time to wait for API requests to complete
        - **Max Search Results**: Maximum number of items to return in search results
        
        #### Troubleshooting
        - If you encounter issues, try resetting to defaults
        - Check the logging level to see more detailed error messages
        """)
