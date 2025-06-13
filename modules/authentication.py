import streamlit as st
from arcgis.gis import GIS
import os
import logging
from typing import Optional

# Configure logging
logger = logging.getLogger("authentication")

def get_gis_object(username: str, password: str, profile: Optional[str] = None) -> GIS:
    """
    Attempts to create and return a GIS object.
    Raises an exception if authentication fails.
    """
    try:
        if profile:
            gis = GIS(profile=profile)
            # If using profile, username/password might not be needed or are part of the profile
            # However, if profile fails, we can try with username/password
            if not gis.logged_in:
                logger.warning(f"Profile '{profile}' failed to authenticate. Attempting with username/password.")
                gis = GIS(username=username, password=password)
        else:
            gis = GIS(username=username, password=password)
        
        if not gis.logged_in:
            raise Exception("Failed to log in with provided credentials.")
        
        logger.info(f"Successfully connected as {gis.properties.user.username}")
        return gis
    except Exception as e:
        logger.error(f"Failed to connect to ArcGIS Online/Portal: {str(e)}")
        raise

def authenticate_from_env() -> GIS:
    """
    Authenticates with ArcGIS Online/Portal using environment variables.
    Raises an exception if required environment variables are missing or authentication fails.
    """
    username = os.environ.get("ARCGIS_USERNAME")
    password = os.environ.get("ARCGIS_PASSWORD")
    profile = os.environ.get("ARCGIS_PROFILE")

    if not username or not password:
        raise ValueError("ARCGIS_USERNAME and ARCGIS_PASSWORD environment variables must be set for headless authentication.")

    st.session_state.username = username # Store username for display if needed
    return get_gis_object(username, password, profile)

def show():
    """Display the authentication interface for Streamlit."""
    st.title("Authentication")
    
    st.markdown("""
    ## ArcGIS Online/Portal Authentication
    
    Connect to ArcGIS Online or Portal to access and modify web maps and layers.
    You can use environment variables or enter your credentials directly.
    """)
    
    auth_method = st.radio(
        "Authentication Method",
        ["Environment Variables", "Manual Entry"],
        index=1  # Set default to "Manual Entry"
    )
    
    username_input = ""
    password_input = ""
    profile_input = ""

    if auth_method == "Environment Variables":
        username_input = os.environ.get("ARCGIS_USERNAME", "")
        password_input = os.environ.get("ARCGIS_PASSWORD", "")
        profile_input = os.environ.get("ARCGIS_PROFILE", "")
        
        st.info("Using credentials from environment variables")
        
        env_status = {
            "ARCGIS_USERNAME": "✅ Set" if username_input else "❌ Not set",
            "ARCGIS_PASSWORD": "✅ Set" if password_input else "❌ Not set",
            "ARCGIS_PROFILE": "✅ Set" if profile_input else "❌ Not set (optional)"
        }
        
        st.write("Environment Variable Status:")
        for var, status in env_status.items():
            st.write(f"- {var}: {status}")
            
        if not username_input or not password_input:
            st.warning("Required environment variables not set. Please set ARCGIS_USERNAME and ARCGIS_PASSWORD, or use Manual Entry.")
    else:
        username_input = st.text_input("Username", value=st.session_state.get("username_manual", ""))
        password_input = st.text_input("Password", type="password", value=st.session_state.get("password_manual", ""))
        profile_input = st.text_input("Profile (optional)", value=st.session_state.get("profile_manual", ""))
        
        st.session_state.username_manual = username_input
        st.session_state.password_manual = password_input
        st.session_state.profile_manual = profile_input
    
    col1, col2 = st.columns([1, 3])
    with col1:
        connect_button = st.button("Connect", type="primary", use_container_width=True)
    
    if connect_button:
        if not username_input or not password_input:
            st.error("Username and password are required")
        else:
            with st.spinner("Connecting to ArcGIS Online/Portal..."):
                try:
                    gis = get_gis_object(username_input, password_input, profile_input)
                    
                    st.session_state.gis = gis
                    st.session_state.authenticated = True
                    st.session_state.username = gis.properties.user.username
                    
                    st.success(f"Connected as {gis.properties.user.username}")
                    
                    st.subheader("User Information")
                    user_info = {
                        "Username": gis.properties.user.username,
                        "Full Name": f"{gis.properties.user.firstName} {gis.properties.user.lastName}",
                        "Email": gis.properties.user.email,
                        "Role": gis.properties.user.role
                    }
                    
                    for key, value in user_info.items():
                        st.write(f"**{key}:** {value}")
                    
                    logger.info(f"User {gis.properties.user.username} authenticated successfully via UI")
                    
                    st.info("You can now use the navigation sidebar to access the tools.")
                    
                except Exception as e:
                    st.error(f"Authentication failed: {str(e)}")
                    logger.error(f"Authentication failed for user {username_input}: {str(e)}")
    
    if st.session_state.authenticated and not connect_button:
        st.success(f"Already connected as {st.session_state.username}")
        
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.gis = None
            st.session_state.username = None
            st.experimental_rerun()
    
    with st.expander("Need Help?"):
        st.markdown("""
        ### Authentication Help
        
        #### Environment Variables
        You can set the following environment variables to avoid entering credentials each time:
        
        ```
        ARCGIS_USERNAME=your_username
        ARCGIS_PASSWORD=your_password
        ARCGIS_PROFILE=your_profile (optional)
        ```
        
        #### Profiles
        The profile parameter is optional and refers to the ArcGIS API for Python profile name.
        Common profiles include:
        
        - `FDC_Admin` - For SWCA's Field Data Collection administration
        - Leave blank for default ArcGIS Online access
        
        #### Troubleshooting
        - Ensure your username and password are correct
        - Check your internet connection
        - Verify that you have the necessary permissions
        - Contact your GIS administrator if problems persist
        """)
