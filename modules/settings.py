import streamlit as st
import logging
import os
import sys
from typing import Dict, Any

# Configure logging
logger = logging.getLogger("settings")

def show():
    """Display the Settings interface"""
    st.title("Settings")
    
    # Display information about settings
    st.markdown("""
    ## Application Settings
    
    Configure global settings for the SWCA GIS Tools application.
    These settings will be applied across all tools.
    """)
    
    # Create tabs for different settings categories
    tab1, tab2, tab3 = st.tabs(["General", "Authentication", "Advanced"])
    
    with tab1:
        show_general_settings()
    
    with tab2:
        show_authentication_settings()
    
    with tab3:
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
    
    # Reset settings
    if st.button("Reset to Defaults", key="reset_general"):
        st.session_state.debug_mode = True
        logging.getLogger().setLevel(logging.INFO)
        st.success("General settings reset to defaults")
        st.experimental_rerun()

def show_authentication_settings():
    """Display authentication settings"""
    st.header("Authentication Settings")
    
    # Environment variables
    st.subheader("Environment Variables")
    
    st.markdown("""
    You can set environment variables to avoid entering credentials each time.
    These variables will be used when you select "Environment Variables" on the Authentication page.
    """)
    
    # Show current environment variables
    env_vars = {
        "ARCGIS_USERNAME": os.environ.get("ARCGIS_USERNAME", ""),
        "ARCGIS_PASSWORD": "********" if os.environ.get("ARCGIS_PASSWORD") else "",
        "ARCGIS_PROFILE": os.environ.get("ARCGIS_PROFILE", "")
    }
    
    # Display environment variables status
    for var, value in env_vars.items():
        status = "✅ Set" if value else "❌ Not set"
        st.write(f"- **{var}**: {status}")
    
    st.info("Environment variables must be set outside of this application. They cannot be set from within the application for security reasons.")
    
    # Session timeout
    st.subheader("Session Settings")
    
    # Session timeout
    session_timeout = st.number_input(
        "Session Timeout (minutes)",
        min_value=5,
        max_value=240,
        value=st.session_state.get("session_timeout", 60),
        help="Time after which the session will expire and require re-authentication"
    )
    
    if session_timeout != st.session_state.get("session_timeout"):
        st.session_state.session_timeout = session_timeout
        st.success(f"Session timeout set to {session_timeout} minutes")
    
    # Logout button
    if st.session_state.get("authenticated", False):
        if st.button("Logout", key="logout_button"):
            st.session_state.authenticated = False
            st.session_state.gis = None
            st.session_state.username = None
            st.success("Logged out successfully")
            st.experimental_rerun()

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
        st.experimental_rerun()

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
        
        #### Authentication Settings
        - **Environment Variables**: Set these outside the application to avoid entering credentials each time
          - ARCGIS_USERNAME: Your ArcGIS username
          - ARCGIS_PASSWORD: Your ArcGIS password
          - ARCGIS_PROFILE: Your ArcGIS profile name (optional)
        - **Session Timeout**: Time after which the session will expire and require re-authentication
        
        #### Advanced Settings
        - **Request Timeout**: Maximum time to wait for API requests to complete
        - **Max Search Results**: Maximum number of items to return in search results
        
        #### Troubleshooting
        - If you encounter issues, try resetting to defaults
        - Check the logging level to see more detailed error messages
        - Ensure your environment variables are set correctly
        """)
