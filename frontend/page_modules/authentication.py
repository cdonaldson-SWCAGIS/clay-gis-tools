"""
Authentication splash screen for Streamlit.
"""

import streamlit as st
import os
from pathlib import Path

from backend.utils.auth import get_gis_object, authenticate_from_env
from backend.utils.logging import get_logger

logger = get_logger("authentication")


def _attempt_env_auth() -> bool:
    """
    Attempt authentication using environment variables.
    Returns True if successful, False otherwise.
    """
    try:
        gis = authenticate_from_env()
        st.session_state.gis = gis
        st.session_state.authenticated = True
        st.session_state.username = gis.properties.user.username
        logger.info(f"User {gis.properties.user.username} authenticated via environment variables")
        return True
    except Exception as e:
        logger.debug(f"Environment authentication not available: {str(e)}")
        return False


def _show_login_form():
    """Display minimal login form for manual authentication."""
    username = st.text_input("Username", key="auth_username")
    password = st.text_input("Password", type="password", key="auth_password")
    
    if st.button("Connect", type="primary", use_container_width=True):
        if not username or not password:
            st.error("Username and password are required")
        else:
            with st.spinner("Connecting..."):
                try:
                    gis = get_gis_object(username, password)
                    st.session_state.gis = gis
                    st.session_state.authenticated = True
                    st.session_state.username = gis.properties.user.username
                    logger.info(f"User {gis.properties.user.username} authenticated via login form")
                    st.rerun()
                except Exception as e:
                    st.error("Authentication failed. Please check your credentials.")
                    logger.error(f"Authentication failed for user {username}: {str(e)}")


def show():
    """Display the authentication splash screen."""
    # Get project root for logo path
    project_root = Path(__file__).parent.parent.parent
    logo_path = project_root / "static" / "icon.svg"
    
    # Center the content with columns
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        # Add vertical spacing
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        
        # Show logo if available
        if logo_path.exists():
            st.image(str(logo_path), width=80)
        
        st.markdown("### Clay AGOL Tools")
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Check if we should attempt env auth (first load only)
        if not st.session_state.get("_env_auth_attempted", False):
            st.session_state._env_auth_attempted = True
            
            with st.spinner("Connecting..."):
                if _attempt_env_auth():
                    st.rerun()
        
        # If still not authenticated, show login form
        if not st.session_state.get("authenticated", False):
            _show_login_form()
