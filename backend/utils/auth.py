"""
Core authentication logic for Clay GIS Tools.
No Streamlit dependencies - pure backend logic.
"""

from arcgis.gis import GIS
import os
import logging
from typing import Optional

from backend.utils.logging import get_logger
from backend.utils.exceptions import AuthenticationError

logger = get_logger("auth")


def get_gis_object(username: str, password: str, profile: Optional[str] = None) -> GIS:
    """
    Attempts to create and return a GIS object.
    Raises an exception if authentication fails.
    
    Args:
        username: ArcGIS username
        password: ArcGIS password
        profile: Optional profile name
        
    Returns:
        Authenticated GIS object
        
    Raises:
        AuthenticationError: If authentication fails
    """
    try:
        gis = GIS(username=username, password=password)
        logger.info(f"Successfully connected as {gis.properties.user.username}")
        return gis
    except Exception as e:
        logger.error(f"Failed to connect to ArcGIS Online/Portal: {str(e)}")
        raise AuthenticationError(f"Authentication failed: {str(e)}") from e


def authenticate_from_env() -> GIS:
    """
    Authenticates with ArcGIS Online/Portal using environment variables.
    Raises an exception if required environment variables are missing or authentication fails.
    
    Returns:
        Authenticated GIS object
        
    Raises:
        ValueError: If required environment variables are missing
        AuthenticationError: If authentication fails
    """
    username = os.environ.get("ARCGIS_USERNAME")
    password = os.environ.get("ARCGIS_PASSWORD")
    profile = os.environ.get("ARCGIS_PROFILE")

    if not username or not password:
        raise ValueError("ARCGIS_USERNAME and ARCGIS_PASSWORD environment variables must be set for headless authentication.")

    return get_gis_object(username, password, profile)
