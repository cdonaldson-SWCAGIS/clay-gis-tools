"""
UI components for tag-based layer selection.
Streamlit components for selecting and managing tagged layers.
"""

import streamlit as st
from typing import List, Optional, Dict, Any
from arcgis.gis import Item

from backend.core.tags import (
    parse_tags,
    search_layers_by_tags,
    extract_layer_coordinate_systems,
    validate_feature_layer_access
)
from backend.utils.config import MAX_LAYER_SELECTION


def show_tagged_layer_selection(
    discovered_items: List[Item], 
    max_selection: int = MAX_LAYER_SELECTION,
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


# Export backend functions for convenience
__all__ = [
    'parse_tags',
    'search_layers_by_tags',
    'extract_layer_coordinate_systems',
    'validate_feature_layer_access',
    'show_tagged_layer_selection',
    'show_coordinate_system_selection',
    'create_tag_search_help'
]
