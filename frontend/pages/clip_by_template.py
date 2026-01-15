"""
Streamlit UI module for the Clip by Template Tag tool.
Provides a comprehensive interface for clipping Feature Layers using template geometries and tag-based discovery.
"""

import streamlit as st
import logging
from typing import Optional, Dict, Any, List
from arcgis.gis import GIS, Item
from arcgis.features import FeatureLayer

from frontend.components.common_operations import (
    ensure_authentication, get_gis_object, show_debug_mode_control,
    show_tool_header, execute_operation_with_status
)
from frontend.components.item_selector import ItemSelector
from frontend.components.tag_selector import (
    parse_tags, search_layers_by_tags, show_tagged_layer_selection,
    show_coordinate_system_selection, create_tag_search_help
)
from backend.core.clip.geometry import BufferUnits
from backend.core.clip.operations import (
    batch_clip_layers, validate_clip_inputs
)
# Note: show_clip_results, create_clip_help_section, show_template_geometry_preview 
# need to be moved to frontend or reimplemented

from backend.utils.logging import get_logger

# Configure logging
logger = get_logger("clip_by_template_tag")


def show() -> None:
    """Main function to display the Clip by Template Tag interface."""
    
    # Show tool header
    show_tool_header(
        title="Clip by Template Tag",
        description="Clip multiple Feature Layers using a template geometry and tag-based layer discovery.",
        icon="✂️"
    )
    
    # Check authentication
    if not ensure_authentication():
        return
    
    gis = get_gis_object()
    if not gis:
        st.error("Failed to get GIS connection")
        return
    
    # Show help sections
    create_clip_help_section()
    create_tag_search_help()
    
    # Initialize session state
    if "clip_results" not in st.session_state:
        st.session_state.clip_results = None
    
    # Main interface sections
    st.markdown("---")
    
    # Section 1: Template Geometry Configuration
    template_config = show_template_geometry_section(gis)
    
    st.markdown("---")
    
    # Section 2: Tagged Layer Discovery
    discovered_items = show_tag_discovery_section(gis)
    
    st.markdown("---")
    
    # Section 3: Layer Selection
    selected_items = show_layer_selection_section(discovered_items)
    
    st.markdown("---")
    
    # Section 4: Output Configuration
    output_config = show_output_configuration_section(selected_items)
    
    st.markdown("---")
    
    # Section 5: Operation Controls
    show_operation_controls_section(template_config, selected_items, output_config, gis)
    
    # Section 6: Results Display
    if st.session_state.clip_results:
        st.markdown("---")
        show_clip_results(st.session_state.clip_results)


def show_template_geometry_section(gis: GIS) -> Dict[str, Any]:
    """
    Display the template geometry configuration section.
    
    Args:
        gis: The authenticated GIS object
        
    Returns:
        Dictionary with template configuration
    """
    st.header("1. Template Geometry Configuration")
    st.write("Select a Feature Layer to use as the clipping template.")
    
    # Template layer selection
    template_selector = ItemSelector(gis, "Feature Layer", "template")
    template_item = template_selector.show(
        title="Select Template Layer",
        help_text="Choose the Feature Layer that will define the clipping boundary.",
        show_item_details=True
    )
    
    template_config = {}
    
    if template_item:
        try:
            # Get the feature layer
            template_layer = FeatureLayer.fromitem(template_item)
            template_config['feature_layer'] = template_layer
            template_config['item'] = template_item
            
            # WHERE clause configuration
            st.subheader("Filter Features (Optional)")
            where_clause = st.text_input(
                "WHERE clause",
                value="1=1",
                placeholder="e.g., STATUS = 'Active' OR AREA > 1000",
                help="SQL WHERE clause to filter template features. Use '1=1' to include all features.",
                key="template_where_clause"
            )
            template_config['where_clause'] = where_clause
            
            # Buffer configuration
            st.subheader("Buffer Configuration")
            col1, col2 = st.columns([2, 1])
            
            with col1:
                buffer_distance = st.number_input(
                    "Buffer Distance",
                    min_value=0.0,
                    value=0.0,
                    step=1.0,
                    help="Distance to buffer the template geometry. Use 0 for no buffer.",
                    key="template_buffer_distance"
                )
                template_config['buffer_distance'] = buffer_distance
            
            with col2:
                buffer_unit = st.selectbox(
                    "Buffer Unit",
                    BufferUnits.get_all_units(),
                    index=0,  # Default to meters
                    key="template_buffer_unit"
                )
                template_config['buffer_unit'] = buffer_unit
            
            # Show template geometry preview
            show_template_geometry_preview(
                template_layer,
                where_clause,
                buffer_distance,
                buffer_unit
            )
            
        except Exception as e:
            st.error(f"Error accessing template layer: {str(e)}")
            logger.error(f"Error in template geometry section: {str(e)}")
    
    return template_config


def show_tag_discovery_section(gis: GIS) -> List[Item]:
    """
    Display the tag-based layer discovery section.
    
    Args:
        gis: The authenticated GIS object
        
    Returns:
        List of discovered Feature Layer items
    """
    st.header("2. Tagged Layer Discovery")
    st.write("Search for Feature Layers using comma-delimited tags.")
    
    # Tag input and search configuration
    col1, col2 = st.columns([3, 1])
    
    with col1:
        tag_string = st.text_input(
            "Tags to Search",
            placeholder="e.g., environmental, water, survey_2024",
            help="Enter comma-separated tags to search for Feature Layers",
            key="tag_search_input"
        )
    
    with col2:
        search_org_only = st.checkbox(
            "Organization Only",
            value=True,
            help="Search within your organization only (unchecked = search public AGOL)",
            key="search_org_only"
        )
    
    discovered_items = []
    
    if tag_string:
        # Parse tags
        tags = parse_tags(tag_string)
        
        if tags:
            st.info(f"Searching for layers with tags: {', '.join(tags)}")
            
            # Search button
            if st.button("🔍 Search for Layers", key="search_layers_btn"):
                with st.spinner("Searching for Feature Layers..."):
                    try:
                        discovered_items = search_layers_by_tags(
                            gis=gis,
                            tags=tags,
                            search_org_only=search_org_only,
                            max_results=50
                        )
                        
                        # Store results in session state
                        st.session_state.discovered_items = discovered_items
                        
                        if discovered_items:
                            st.success(f"Found {len(discovered_items)} Feature Layers with matching tags")
                        else:
                            st.warning("No Feature Layers found with the specified tags")
                            
                    except Exception as e:
                        st.error(f"Error searching for layers: {str(e)}")
                        logger.error(f"Error in tag discovery: {str(e)}")
        else:
            st.warning("Please enter valid tags separated by commas")
    
    # Get discovered items from session state if available
    if "discovered_items" in st.session_state:
        discovered_items = st.session_state.discovered_items
    
    # Show discovery results summary
    if discovered_items:
        st.write(f"**Discovery Results:** {len(discovered_items)} Feature Layers found")
        
        # Show summary of discovered layers
        with st.expander("View Discovered Layers", expanded=False):
            for item in discovered_items:
                st.write(f"• **{item.title}** (by {item.owner}) - Tags: {', '.join(item.tags) if item.tags else 'None'}")
    
    return discovered_items


def show_layer_selection_section(discovered_items: List[Item]) -> List[Item]:
    """
    Display the layer selection section.
    
    Args:
        discovered_items: List of discovered Feature Layer items
        
    Returns:
        List of selected Feature Layer items
    """
    st.header("3. Layer Selection")
    
    if not discovered_items:
        st.info("Search for layers first to see selection options")
        return []
    
    # Show layer selection interface
    selected_items = show_tagged_layer_selection(
        discovered_items=discovered_items,
        max_selection=10,
        key_prefix="clip_layers"
    )
    
    return selected_items


def show_output_configuration_section(selected_items: List[Item]) -> Dict[str, Any]:
    """
    Display the output configuration section.
    
    Args:
        selected_items: List of selected Feature Layer items
        
    Returns:
        Dictionary with output configuration
    """
    st.header("4. Output Configuration")
    
    output_config = {}
    
    if not selected_items:
        st.info("Select layers first to configure output settings")
        return output_config
    
    # Coordinate system selection
    selected_crs = show_coordinate_system_selection(
        selected_items=selected_items,
        key_prefix="output_crs"
    )
    
    if selected_crs:
        output_config['spatial_reference'] = selected_crs['spatial_reference']
        output_config['crs_info'] = selected_crs
    
    # Output naming preview
    st.subheader("Output Naming")
    st.write("**Naming Convention:** `{original_layer_name}_clipped`")
    
    if selected_items:
        st.write("**Preview of output layer names:**")
        for item in selected_items[:3]:  # Show first 3 as preview
            st.write(f"• {item.title} → **{item.title}_clipped**")
        
        if len(selected_items) > 3:
            st.write(f"• ... and {len(selected_items) - 3} more layers")
    
    # Output location info
    st.info("📁 Output layers will be saved to your root AGOL folder")
    
    return output_config


def show_operation_controls_section(
    template_config: Dict[str, Any],
    selected_items: List[Item],
    output_config: Dict[str, Any],
    gis: GIS
) -> None:
    """
    Display the operation controls section.
    
    Args:
        template_config: Template geometry configuration
        selected_items: Selected Feature Layer items
        output_config: Output configuration
        gis: The authenticated GIS object
    """
    st.header("5. Run Clipping Operation")
    
    # Debug mode control
    debug_mode = show_debug_mode_control("clip_operation")
    
    # Validation
    template_layer = template_config.get('feature_layer')
    output_crs = output_config.get('spatial_reference', {})
    
    is_valid, validation_errors = validate_clip_inputs(
        template_layer=template_layer,
        target_items=selected_items,
        output_crs=output_crs
    )
    
    # Show validation status
    if validation_errors:
        st.error("Please fix the following issues before running:")
        for error in validation_errors:
            st.write(f"• {error}")
    else:
        st.success("✅ Configuration is valid and ready to run")
    
    # Operation summary
    if template_layer and selected_items:
        st.subheader("Operation Summary")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Template Layer", template_config.get('item', {}).get('title', 'Unknown'))
        with col2:
            st.metric("Target Layers", len(selected_items))
        with col3:
            buffer_dist = template_config.get('buffer_distance', 0)
            buffer_unit = template_config.get('buffer_unit', 'meters')
            buffer_text = f"{buffer_dist} {buffer_unit}" if buffer_dist > 0 else "None"
            st.metric("Buffer", buffer_text)
    
    # Run button
    col1, col2 = st.columns([1, 3])
    
    with col1:
        run_button = st.button(
            "🚀 Run Clipping",
            disabled=not is_valid,
            type="primary",
            key="run_clip_operation"
        )
    
    with col2:
        if debug_mode:
            st.info("🧪 Debug mode: Operations will be simulated")
        else:
            st.warning("⚠️ Live mode: New layers will be created in AGOL")
    
    # Execute operation
    if run_button and is_valid:
        # Clear previous results
        st.session_state.clip_results = None
        
        # Execute the clipping operation
        results = execute_operation_with_status(
            operation_name="Clip by Template Tag",
            operation_func=batch_clip_layers,
            operation_args=(template_config, selected_items, output_config, gis, debug_mode),
            success_message="Clipping operation completed successfully",
            error_message="Clipping operation failed",
            show_debug_notice=True
        )
        
        # Store results
        if results:
            st.session_state.clip_results = results
            
            # Show immediate summary
            successful_count = sum(1 for r in results if r.success)
            failed_count = len(results) - successful_count
            
            if successful_count > 0:
                st.success(f"✅ Successfully processed {successful_count} layers")
            if failed_count > 0:
                st.error(f"❌ Failed to process {failed_count} layers")


def clear_session_data() -> None:
    """Clear all session data related to the clipping tool."""
    keys_to_clear = [
        'discovered_items',
        'clip_results',
        'tagged_layers_selections',
        'template_item',
        'output_crs_select'
    ]
    
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    st.success("Session data cleared")


def show_advanced_options() -> None:
    """Show advanced configuration options."""
    with st.expander("⚙️ Advanced Options", expanded=False):
        st.markdown("""
        ### Advanced Configuration
        
        **Performance Settings:**
        - Maximum 10 layers can be processed simultaneously
        - Large layers may take longer to process
        - Consider using filters to reduce feature counts
        
        **Coordinate System Handling:**
        - Template geometry is automatically projected to output CRS
        - All clipped features will be in the selected output CRS
        - Mixed coordinate systems are handled automatically
        
        **Error Recovery:**
        - Failed layers are skipped automatically
        - Operation continues with remaining layers
        - Detailed error messages are provided for troubleshooting
        
        **Output Management:**
        - Output layers are created in your root AGOL folder
        - Naming conflicts are handled automatically
        - Original layer metadata is preserved where possible
        """)
        
        # Clear session data button
        if st.button("🗑️ Clear Session Data", key="clear_session_data"):
            clear_session_data()


# Add advanced options to the main interface
def show_with_advanced() -> None:
    """Show the main interface with advanced options."""
    show()
    show_advanced_options()


# Export the main function
if __name__ == "__main__":
    show_with_advanced()
