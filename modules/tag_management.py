"""
Tag management utilities for discovering and filtering ArcGIS items by tags.
Provides functionality to search for Feature Layers based on comma-delimited tags.
"""

import streamlit as st
import logging
from typing import List, Optional, Dict, Any, Tuple
from arcgis.gis import GIS, Item
from arcgis.features import FeatureLayer

# Configure logging
logger = logging.getLogger("tag_management")


def parse_tags(tag_string: str) -> List[str]:
    """
    Parse comma-delimited tag string into a list of individual tags.
    
    Args:
        tag_string: Comma-delimited string of tags
        
    Returns:
        List of cleaned tag strings
    """
    if not tag_string:
        return []
    
    # Split by comma and clean up whitespace
    tags = [tag.strip() for tag in tag_string.split(",") if tag.strip()]
    logger.debug(f"Parsed tags: {tags}")
    return tags


def search_layers_by_tags(
    gis: GIS, 
    tags: List[str], 
    search_org_only: bool = True, 
    max_results: int = 50
) -> List[Item]:
    """
    Search for Feature Layers containing any of the specified tags.
    
    Args:
        gis: The authenticated GIS object
        tags: List of tags to search for
        search_org_only: Whether to search within organization only
        max_results: Maximum number of results to return
        
    Returns:
        List of Feature Layer items that contain any of the specified tags
    """
    if not tags:
        logger.warning("No tags provided for search")
        return []
    
    matching_items = []
    
    try:
        # Create search query for tags
        # Use OR logic to find items with any of the specified tags
        tag_queries = [f'tags:"{tag}"' for tag in tags]
        tag_query = " OR ".join(tag_queries)
        
        # Combine with item type filter
        full_query = f"({tag_query}) AND type:\"Feature Layer\""
        
        logger.info(f"Searching with query: {full_query}")
        logger.info(f"Search scope: {'Organization only' if search_org_only else 'Public AGOL'}")
        
        # Perform search
        search_results = gis.content.search(
            query=full_query,
            item_type="Feature Layer",
            max_items=max_results,
            outside_org=not search_org_only
        )
        
        # Filter results to ensure they actually contain the tags
        for item in search_results:
            if item.tags and any(tag.lower() in [t.lower() for t in item.tags] for tag in tags):
                matching_items.append(item)
                logger.debug(f"Found matching layer: {item.title} (tags: {item.tags})")
        
        logger.info(f"Found {len(matching_items)} Feature Layers with matching tags")
        
    except Exception as e:
        logger.error(f"Error searching for layers by tags: {str(e)}")
        raise
    
    return matching_items


def extract_layer_coordinate_systems(items: List[Item]) -> List[Dict[str, Any]]:
    """
    Extract unique coordinate systems from a list of Feature Layer items.
    
    Args:
        items: List of Feature Layer items
        
    Returns:
        List of coordinate system dictionaries with 'name', 'wkid', and 'item_title'
    """
    coordinate_systems = []
    seen_wkids = set()
    
    for item in items:
        try:
            # Get the feature layer
            feature_layer = FeatureLayer.fromitem(item)
            
            # Extract spatial reference information
            if hasattr(feature_layer, 'properties') and feature_layer.properties:
                extent = feature_layer.properties.get('extent')
                if extent and 'spatialReference' in extent:
                    spatial_ref = extent['spatialReference']
                    wkid = spatial_ref.get('wkid')
                    
                    if wkid and wkid not in seen_wkids:
                        # Try to get a readable name for the coordinate system
                        crs_name = spatial_ref.get('latestWkid', wkid)
                        
                        # Common coordinate system names
                        common_names = {
                            4326: "WGS 84 (Geographic)",
                            3857: "Web Mercator",
                            102100: "Web Mercator Auxiliary Sphere",
                            4269: "NAD 83 (Geographic)",
                            3826: "TWD97 / TM2 zone 121",
                            2154: "RGF93 / Lambert-93"
                        }
                        
                        display_name = common_names.get(wkid, f"EPSG:{wkid}")
                        
                        coordinate_systems.append({
                            'name': display_name,
                            'wkid': wkid,
                            'item_title': item.title,
                            'spatial_reference': spatial_ref
                        })
                        
                        seen_wkids.add(wkid)
                        logger.debug(f"Found CRS {display_name} (WKID: {wkid}) from layer: {item.title}")
        
        except Exception as e:
            logger.warning(f"Could not extract coordinate system from layer {item.title}: {str(e)}")
            continue
    
    logger.info(f"Extracted {len(coordinate_systems)} unique coordinate systems")
    return coordinate_systems


def validate_feature_layer_access(gis: GIS, item: Item) -> Tuple[bool, str]:
    """
    Validate that a Feature Layer item is accessible and can be used for clipping.
    
    Args:
        gis: The authenticated GIS object
        item: The Feature Layer item to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check if item exists and is accessible
        if not item:
            return False, "Item not found"
        
        # Check if it's actually a Feature Layer
        if item.type != "Feature Layer":
            return False, f"Item is not a Feature Layer (type: {item.type})"
        
        # Try to create a FeatureLayer object
        feature_layer = FeatureLayer.fromitem(item)
        
        # Check if we can access basic properties
        if not hasattr(feature_layer, 'properties') or not feature_layer.properties:
            return False, "Cannot access layer properties"
        
        # Check if layer has geometry
        geometry_type = feature_layer.properties.get('geometryType')
        if not geometry_type:
            return False, "Layer does not have geometry information"
        
        # Check if layer is queryable
        capabilities = feature_layer.properties.get('capabilities', '')
        if 'Query' not in capabilities:
            return False, "Layer does not support querying"
        
        logger.debug(f"Layer {item.title} validated successfully")
        return True, "Valid"
        
    except Exception as e:
        error_msg = f"Error validating layer: {str(e)}"
        logger.warning(f"Validation failed for layer {item.title}: {error_msg}")
        return False, error_msg


def show_tagged_layer_selection(
    discovered_items: List[Item], 
    max_selection: int = 10,
    key_prefix: str = "tagged_layers"
) -> List[Item]:
    """
    Display a selection interface for tagged layers with validation.
    
    Args:
        discovered_items: List of discovered Feature Layer items
        max_selection: Maximum number of layers that can be selected
        key_prefix: Unique prefix for Streamlit widget keys
        
    Returns:
        List of selected Feature Layer items
    """
    if not discovered_items:
        st.warning("No Feature Layers found with the specified tags")
        return []
    
    st.subheader(f"Select Layers to Clip (Maximum {max_selection})")
    
    # Initialize session state for selections
    selection_key = f"{key_prefix}_selections"
    if selection_key not in st.session_state:
        st.session_state[selection_key] = {}
    
    selected_items = []
    
    # Show selection interface
    st.write(f"Found {len(discovered_items)} Feature Layers with matching tags:")
    
    # Create columns for better layout
    col1, col2 = st.columns([3, 1])
    
    with col1:
        for i, item in enumerate(discovered_items):
            # Create unique key for each checkbox
            checkbox_key = f"{key_prefix}_item_{i}_{item.id}"
            
            # Get current selection state
            current_selection = st.session_state[selection_key].get(item.id, False)
            
            # Count current selections
            current_count = sum(1 for selected in st.session_state[selection_key].values() if selected)
            
            # Disable checkbox if max selections reached and this item isn't selected
            disabled = current_count >= max_selection and not current_selection
            
            # Show checkbox with item information
            selected = st.checkbox(
                f"**{item.title}**",
                value=current_selection,
                disabled=disabled,
                key=checkbox_key,
                help=f"Owner: {item.owner}\nTags: {', '.join(item.tags) if item.tags else 'None'}\nModified: {item.modified.strftime('%Y-%m-%d') if item.modified else 'Unknown'}"
            )
            
            # Update selection state
            st.session_state[selection_key][item.id] = selected
            
            if selected:
                selected_items.append(item)
            
            # Show item details
            with st.expander(f"Details for {item.title}", expanded=False):
                col_detail1, col_detail2 = st.columns(2)
                with col_detail1:
                    st.write(f"**Owner:** {item.owner}")
                    st.write(f"**Type:** {item.type}")
                    st.write(f"**ID:** {item.id}")
                with col_detail2:
                    st.write(f"**Created:** {item.created.strftime('%Y-%m-%d') if item.created else 'Unknown'}")
                    st.write(f"**Modified:** {item.modified.strftime('%Y-%m-%d') if item.modified else 'Unknown'}")
                    st.write(f"**Views:** {getattr(item, 'numViews', 'Unknown')}")
                
                if item.tags:
                    st.write(f"**Tags:** {', '.join(item.tags)}")
                
                if hasattr(item, 'description') and item.description:
                    st.write(f"**Description:** {item.description}")
    
    with col2:
        # Show selection summary
        current_count = len(selected_items)
        st.metric("Selected", f"{current_count}/{max_selection}")
        
        if current_count >= max_selection:
            st.warning(f"Maximum {max_selection} layers selected")
        elif current_count > 0:
            st.success(f"{current_count} layer{'s' if current_count != 1 else ''} selected")
        
        # Clear selections button
        if st.button("Clear All", key=f"{key_prefix}_clear"):
            st.session_state[selection_key] = {}
            st.rerun()
    
    return selected_items


def show_coordinate_system_selection(
    selected_items: List[Item],
    key_prefix: str = "crs_selection"
) -> Optional[Dict[str, Any]]:
    """
    Display coordinate system selection interface based on selected layers.
    
    Args:
        selected_items: List of selected Feature Layer items
        key_prefix: Unique prefix for Streamlit widget keys
        
    Returns:
        Selected coordinate system dictionary or None
    """
    if not selected_items:
        st.info("Select layers first to see available coordinate systems")
        return None
    
    st.subheader("Output Coordinate System")
    
    # Extract coordinate systems from selected layers
    coordinate_systems = extract_layer_coordinate_systems(selected_items)
    
    if not coordinate_systems:
        st.error("Could not determine coordinate systems from selected layers")
        return None
    
    # Create options for selectbox
    crs_options = {}
    for crs in coordinate_systems:
        display_name = f"{crs['name']} (from {crs['item_title']})"
        crs_options[display_name] = crs
    
    # Show selection interface
    selected_display = st.selectbox(
        "Choose output coordinate system",
        list(crs_options.keys()),
        index=0,  # Default to first option
        key=f"{key_prefix}_select",
        help="The coordinate system that will be used for the clipped output layers"
    )
    
    if selected_display:
        selected_crs = crs_options[selected_display]
        
        # Show details about selected CRS
        with st.expander("Coordinate System Details", expanded=False):
            st.write(f"**Name:** {selected_crs['name']}")
            st.write(f"**WKID:** {selected_crs['wkid']}")
            st.write(f"**Source Layer:** {selected_crs['item_title']}")
            
            if 'spatial_reference' in selected_crs:
                st.json(selected_crs['spatial_reference'])
        
        return selected_crs
    
    return None


def create_tag_search_help() -> None:
    """Create a help section for tag search functionality."""
    with st.expander("ℹ️ Tag Search Help", expanded=False):
        st.markdown("""
        ### How Tag Search Works
        
        **Tag Format:**
        - Enter tags separated by commas (e.g., `project_a, survey_data, 2024`)
        - Tags are case-insensitive
        - Spaces around commas are automatically removed
        
        **Search Behavior:**
        - Finds Feature Layers that contain ANY of the specified tags
        - Uses OR logic (layer needs only one matching tag)
        - Searches in item metadata tags, not layer attribute data
        
        **Search Scope:**
        - **Organization Only:** Searches within your organization's content
        - **Public AGOL:** Searches all publicly accessible content on ArcGIS Online
        
        **Examples:**
        - `environmental, water` - Finds layers tagged with either "environmental" OR "water"
        - `project_123` - Finds layers tagged with "project_123"
        - `survey, field_data, 2024` - Finds layers with any of these three tags
        """)
