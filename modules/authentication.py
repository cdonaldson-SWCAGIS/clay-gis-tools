import streamlit as st
from arcgis.gis import GIS
import os
import logging

# Configure logging
logger = logging.getLogger("authentication")

def show():
    """Display the authentication interface"""
    st.title("Authentication")
    
    # Display information about authentication
    st.markdown("""
    ## ArcGIS Online/Portal Authentication
    
    Connect to ArcGIS Online or Portal to access and modify web maps and layers.
    You can use environment variables or enter your credentials directly.
    """)
    
    # Authentication method selection
    auth_method = st.radio(
        "Authentication Method",
        ["Environment Variables", "Manual Entry"]
    )
    
    # Get credentials based on selected method
    if auth_method == "Environment Variables":
        username = os.environ.get("ARCGIS_USERNAME", "")
        password = os.environ.get("ARCGIS_PASSWORD", "")
        profile = os.environ.get("ARCGIS_PROFILE", "")
        
        st.info("Using credentials from environment variables")
        
        # Show environment variable status
        env_status = {
            "ARCGIS_USERNAME": "✅ Set" if username else "❌ Not set",
            "ARCGIS_PASSWORD": "✅ Set" if password else "❌ Not set",
            "ARCGIS_PROFILE": "✅ Set" if profile else "❌ Not set (optional)"
        }
        
        st.write("Environment Variable Status:")
        for var, status in env_status.items():
            st.write(f"- {var}: {status}")
            
        if not username or not password:
            st.warning("Required environment variables not set. Please set ARCGIS_USERNAME and ARCGIS_PASSWORD, or use Manual Entry.")
    else:
        # Manual credential entry
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        profile = st.text_input("Profile (optional)")
    
    # Connection button
    col1, col2 = st.columns([1, 3])
    with col1:
        connect_button = st.button("Connect", type="primary", use_container_width=True)
    
    # Handle connection attempt
    if connect_button:
        if not username or not password:
            st.error("Username and password are required")
        else:
            with st.spinner("Connecting to ArcGIS Online/Portal..."):
                try:
                    # Attempt to connect to ArcGIS Online/Portal
                    gis = GIS(username=username, password=password, profile=profile)
                    
                    # Store connection in session state
                    st.session_state.gis = gis
                    st.session_state.authenticated = True
                    st.session_state.username = username
                    
                    # Display success message
                    st.success(f"Connected as {gis.properties.user.username}")
                    
                    # Show user information
                    st.subheader("User Information")
                    user_info = {
                        "Username": gis.properties.user.username,
                        "Full Name": f"{gis.properties.user.firstName} {gis.properties.user.lastName}",
                        "Email": gis.properties.user.email,
                        "Role": gis.properties.user.role
                    }
                    
                    for key, value in user_info.items():
                        st.write(f"**{key}:** {value}")
                    
                    # Log successful authentication
                    logger.info(f"User {username} authenticated successfully")
                    
                    # Prompt to navigate to tools
                    st.info("You can now use the navigation sidebar to access the tools.")
                    
                except Exception as e:
                    # Handle authentication failure
                    st.error(f"Authentication failed: {str(e)}")
                    logger.error(f"Authentication failed for user {username}: {str(e)}")
    
    # Show authenticated status if already logged in
    if st.session_state.authenticated and not connect_button:
        st.success(f"Already connected as {st.session_state.username}")
        
        # Logout button
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.gis = None
            st.session_state.username = None
            st.experimental_rerun()
    
    # Help information
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
