import streamlit as st
import logging
import sys
import os
from typing import List, Optional, Dict, Any

# Configure logging
logger = logging.getLogger("webmap_forms")

# Import the patch_webmap_forms module
try:
    from src import patch_webmap_forms
except ImportError:
    st.error("Failed to import patch_webmap_forms module. Make sure the src directory is in your Python path.")
    sys.exit(1)

def show():
    """Display the Web Map Forms interface"""
    st.title("Web Map Forms")
    
    # Check authentication
    if not st.session_state.authenticated:
        st.warning("Please authenticate first")
        st.info("Use the navigation sidebar to go to the Authentication page")
        return
    
    # Display information about the tool
    st.markdown("""
    ## Web Map Forms Utility
    
    This tool allows you to update form configurations in ArcGIS web maps.
    You can add or update form elements and propagate form configurations between layers.
    """)
    
    # Create tabs for different operations
    tab1, tab2 = st.tabs(["Update Field", "Propagate Forms"])
    
    with tab1:
        show_update_field()
    
    with tab2:
        show_propagate_forms()
    
    # Show help information
    show_help()

def show_update_field():
    """Display the interface for updating a field in forms"""
    st.header("Update Field in Forms")
    
    # Web map selection
    st.subheader("Web Map Selection")
    
    # Option to search for web maps
    use_search = st.checkbox("Search for web maps", value=False, key="update_search")
    
    if use_search:
        # Search for web maps
        search_query = st.text_input("Search query", placeholder="Enter search terms", key="update_search_query")
        
        if search_query:
            with st.spinner("Searching for web maps..."):
                try:
                    # Search for web maps using the GIS object
                    items = st.session_state.gis.content.search(
                        query=search_query, 
                        item_type="Web Map",
                        max_items=25
                    )
                    
                    if items:
                        # Create a dictionary of web map titles and IDs
                        options = {f"{item.title} ({item.id})": item.id for item in items}
                        
                        # Create a selectbox for the user to choose a web map
                        selected = st.selectbox(
                            "Select a web map",
                            list(options.keys()),
                            index=None,
                            placeholder="Choose a web map...",
                            key="update_webmap_select"
                        )
                        
                        if selected:
                            webmap_id = options[selected]
                            st.session_state.update_webmap_id = webmap_id
                    else:
                        st.info("No web maps found matching your search criteria")
                except Exception as e:
                    st.error(f"Error searching for web maps: {str(e)}")
                    logger.error(f"Error searching for web maps: {str(e)}")
    else:
        # Direct ID input
        webmap_id = st.text_input(
            "Web Map ID",
            value=st.session_state.get("update_webmap_id", ""),
            placeholder="Enter the web map item ID",
            key="update_webmap_id_input"
        )
        
        if webmap_id:
            st.session_state.update_webmap_id = webmap_id
    
    # Field parameters
    st.subheader("Field Parameters")
    
    # Field name
    field_name = st.text_input(
        "Field Name",
        value=st.session_state.get("field_name", "project_number"),
        help="The name of the field to add/update in forms",
        key="update_field_name"
    )
    
    if field_name:
        st.session_state.field_name = field_name
    
    # Expression name
    expression_name = st.text_input(
        "Expression Name",
        value=st.session_state.get("expression_name", "expr/set-project-number"),
        help="The name of the expression to use for the field value",
        key="update_expression_name"
    )
    
    if expression_name:
        st.session_state.expression_name = expression_name
    
    # Expression value
    expression_value = st.text_input(
        "Expression Value (optional)",
        value=st.session_state.get("expression_value", ""),
        help="The value for the expression (random if not provided)",
        key="update_expression_value"
    )
    
    if expression_value:
        st.session_state.expression_value = expression_value
    
    # Group name
    group_name = st.text_input(
        "Group Name",
        value=st.session_state.get("group_name", "Metadata"),
        help="The name of the group to add the field to",
        key="update_group_name"
    )
    
    if group_name:
        st.session_state.group_name = group_name
    
    # Field label
    field_label = st.text_input(
        "Field Label (optional)",
        value=st.session_state.get("field_label", ""),
        help="The label for the field (derived from field name if not provided)",
        key="update_field_label"
    )
    
    if field_label:
        st.session_state.field_label = field_label
    
    # Editable
    editable = st.checkbox(
        "Editable",
        value=st.session_state.get("editable", False),
        help="Whether the field should be editable",
        key="update_editable"
    )
    
    st.session_state.editable = editable
    
    # Debug mode
    debug_mode = st.checkbox(
        "Debug Mode (simulate updates)",
        value=st.session_state.get("debug_mode", True),
        help="When enabled, changes will be simulated but not saved to the server",
        key="update_debug_mode"
    )
    
    st.session_state.debug_mode = debug_mode
    
    # Execute button
    col1, col2 = st.columns([1, 3])
    with col1:
        update_button = st.button("Update Web Map Forms", type="primary", use_container_width=True, key="update_button")
    
    # Handle update request
    if update_button:
        if not st.session_state.get("update_webmap_id"):
            st.error("Please provide a Web Map ID")
        elif not field_name:
            st.error("Please provide a Field Name")
        elif not expression_name:
            st.error("Please provide an Expression Name")
        else:
            # Execute the update
            execute_form_update(
                st.session_state.update_webmap_id,
                field_name,
                expression_name,
                expression_value,
                group_name,
                field_label,
                editable,
                debug_mode
            )

def show_propagate_forms():
    """Display the interface for propagating form elements between layers"""
    st.header("Propagate Form Elements")
    
    # Web map selection
    st.subheader("Web Map Selection")
    
    # Option to search for web maps
    use_search = st.checkbox("Search for web maps", value=False, key="propagate_search")
    
    if use_search:
        # Search for web maps
        search_query = st.text_input("Search query", placeholder="Enter search terms", key="propagate_search_query")
        
        if search_query:
            with st.spinner("Searching for web maps..."):
                try:
                    # Search for web maps using the GIS object
                    items = st.session_state.gis.content.search(
                        query=search_query, 
                        item_type="Web Map",
                        max_items=25
                    )
                    
                    if items:
                        # Create a dictionary of web map titles and IDs
                        options = {f"{item.title} ({item.id})": item.id for item in items}
                        
                        # Create a selectbox for the user to choose a web map
                        selected = st.selectbox(
                            "Select a web map",
                            list(options.keys()),
                            index=None,
                            placeholder="Choose a web map...",
                            key="propagate_webmap_select"
                        )
                        
                        if selected:
                            webmap_id = options[selected]
                            st.session_state.propagate_webmap_id = webmap_id
                    else:
                        st.info("No web maps found matching your search criteria")
                except Exception as e:
                    st.error(f"Error searching for web maps: {str(e)}")
                    logger.error(f"Error searching for web maps: {str(e)}")
    else:
        # Direct ID input
        webmap_id = st.text_input(
            "Web Map ID",
            value=st.session_state.get("propagate_webmap_id", ""),
            placeholder="Enter the web map item ID",
            key="propagate_webmap_id_input"
        )
        
        if webmap_id:
            st.session_state.propagate_webmap_id = webmap_id
    
    # Source layer
    st.subheader("Source Layer")
    source_layer = st.text_input(
        "Source Layer Name",
        value=st.session_state.get("source_layer", ""),
        help="The name of the source layer to copy configurations from",
        key="propagate_source_layer"
    )
    
    if source_layer:
        st.session_state.source_layer = source_layer
    
    # Target layers
    st.subheader("Target Layers")
    use_specific_targets = st.checkbox(
        "Specify Target Layers",
        value=st.session_state.get("use_specific_targets", False),
        help="If checked, only the specified layers will be updated",
        key="propagate_use_specific_targets"
    )
    
    st.session_state.use_specific_targets = use_specific_targets
    
    target_layers = None
    if use_specific_targets:
        target_input = st.text_area(
            "Target Layer Names (one per line)",
            value=st.session_state.get("target_input", ""),
            help="Enter the names of the target layers, one per line",
            key="propagate_target_input"
        )
        
        if target_input:
            st.session_state.target_input = target_input
            target_layers = [layer.strip() for layer in target_input.split("\n") if layer.strip()]
    
    # Fields
    st.subheader("Fields")
    use_specific_fields = st.checkbox(
        "Specify Fields",
        value=st.session_state.get("use_specific_fields", False),
        help="If checked, only the specified fields will be propagated",
        key="propagate_use_specific_fields"
    )
    
    st.session_state.use_specific_fields = use_specific_fields
    
    field_names = None
    if use_specific_fields:
        field_input = st.text_area(
            "Field Names (one per line)",
            value=st.session_state.get("field_input", ""),
            help="Enter the names of the fields to propagate, one per line",
            key="propagate_field_input"
        )
        
        if field_input:
            st.session_state.field_input = field_input
            field_names = [field.strip() for field in field_input.split("\n") if field.strip()]
    
    # Debug mode
    debug_mode = st.checkbox(
        "Debug Mode (simulate updates)",
        value=st.session_state.get("debug_mode", True),
        help="When enabled, changes will be simulated but not saved to the server",
        key="propagate_debug_mode"
    )
    
    st.session_state.debug_mode = debug_mode
    
    # Execute button
    col1, col2 = st.columns([1, 3])
    with col1:
        propagate_button = st.button("Propagate Form Elements", type="primary", use_container_width=True, key="propagate_button")
    
    # Handle propagate request
    if propagate_button:
        if not st.session_state.get("propagate_webmap_id"):
            st.error("Please provide a Web Map ID")
        elif not source_layer:
            st.error("Please provide a Source Layer Name")
        else:
            # Execute the propagation
            execute_form_propagation(
                st.session_state.propagate_webmap_id,
                source_layer,
                target_layers,
                field_names,
                debug_mode
            )

def execute_form_update(
    webmap_id: str,
    field_name: str,
    expression_name: str,
    expression_value: Optional[str],
    group_name: str,
    field_label: Optional[str],
    editable: bool,
    debug_mode: bool
) -> None:
    """
    Execute a form update on a web map
    
    Args:
        webmap_id: The ID of the web map to update
        field_name: The name of the field to add/update
        expression_name: The name of the expression to use
        expression_value: The value for the expression (random if not provided)
        group_name: The name of the group to add the element to
        field_label: The label for the field (derived from field name if not provided)
        editable: Whether the field should be editable
        debug_mode: Whether to simulate updates without saving changes
    """
    # Create a status container
    status = st.empty()
    status.info("Starting form update process...")
    
    # Create a progress bar
    progress_bar = st.progress(0)
    
    try:
        # Set debug mode
        patch_webmap_forms.DEBUG_MODE = debug_mode
        
        # Update progress
        progress_bar.progress(25)
        status.info("Retrieving web map...")
        
        # Get the web map item
        webmap_item = patch_webmap_forms.get_webmap_item(webmap_id)
        
        if not webmap_item:
            status.error(f"Web map with ID {webmap_id} was not found")
            progress_bar.empty()
            return
        
        # Update progress
        progress_bar.progress(50)
        status.info(f"Processing web map: {webmap_item.title}...")
        
        # Update the web map forms
        updated_layers = patch_webmap_forms.update_webmap_forms(
            webmap_id,
            field_name,
            expression_name,
            expression_value,
            group_name,
            field_label,
            editable
        )
        
        # Update progress
        progress_bar.progress(100)
        
        # Display results
        if updated_layers:
            status.success(f"Successfully updated {len(updated_layers)} layers")
            
            # Show layer details
            st.subheader("Updated Layers")
            for i, layer_url in enumerate(updated_layers, 1):
                st.write(f"{i}. {layer_url}")
            
            if debug_mode:
                st.info("Running in DEBUG mode - changes were simulated and not saved to the server")
            else:
                st.success("Changes were verified and saved to the server")
        else:
            status.warning("No layers were updated")
            st.info("Note: expressionInfos were still added to the web map")
            
            if not debug_mode:
                st.error(
                    "Possible issues:\n"
                    "  • The web map may not contain layers with formInfo\n"
                    f"  • The layers may not have the '{field_name}' field\n"
                    "  • The server may not have accepted the changes\n"
                    "  • There might be permission issues with the web map"
                )
                
                st.info("Try running with Debug Mode enabled to see more details")
    except Exception as e:
        status.error(f"Error updating web map forms: {str(e)}")
        logger.error(f"Error updating web map forms {webmap_id}: {str(e)}")
        progress_bar.empty()

def execute_form_propagation(
    webmap_id: str,
    source_layer: str,
    target_layers: Optional[List[str]],
    field_names: Optional[List[str]],
    debug_mode: bool
) -> None:
    """
    Execute a form element propagation on a web map
    
    Args:
        webmap_id: The ID of the web map
        source_layer: The name of the source layer to copy configurations from
        target_layers: Optional list of target layer names (if None, all layers are considered)
        field_names: Optional list of field names to propagate (if None, all matching fields are propagated)
        debug_mode: Whether to simulate updates without saving changes
    """
    # Create a status container
    status = st.empty()
    status.info("Starting form element propagation...")
    
    # Create a progress bar
    progress_bar = st.progress(0)
    
    try:
        # Set debug mode
        patch_webmap_forms.DEBUG_MODE = debug_mode
        
        # Update progress
        progress_bar.progress(25)
        status.info("Retrieving web map...")
        
        # Get the web map item
        webmap_item = patch_webmap_forms.get_webmap_item(webmap_id)
        
        if not webmap_item:
            status.error(f"Web map with ID {webmap_id} was not found")
            progress_bar.empty()
            return
        
        # Update progress
        progress_bar.progress(50)
        status.info(f"Processing web map: {webmap_item.title}...")
        
        # Propagate form elements
        updated_layers = patch_webmap_forms.propagate_form_elements(
            webmap_id,
            source_layer,
            target_layers,
            field_names
        )
        
        # Update progress
        progress_bar.progress(100)
        
        # Display results
        if updated_layers:
            status.success(f"Successfully updated {len(updated_layers)} layers")
            
            # Show layer details
            st.subheader("Updated Layers")
            for layer_name, fields in updated_layers.items():
                st.write(f"**{layer_name}**: {', '.join(fields)}")
            
            if debug_mode:
                st.info("Running in DEBUG mode - changes were simulated and not saved to the server")
            else:
                st.success("Changes were verified and saved to the server")
        else:
            status.warning("No layers were updated")
            
            if not debug_mode:
                st.error(
                    "Possible issues:\n"
                    f"  • The source layer '{source_layer}' may not exist in the web map\n"
                    "  • The source layer may not have any form elements\n"
                    "  • The target layers may not have matching fields\n"
                    "  • The server may not have accepted the changes\n"
                    "  • There might be permission issues with the web map"
                )
                
                st.info("Try running with Debug Mode enabled to see more details")
    except Exception as e:
        status.error(f"Error propagating form elements: {str(e)}")
        logger.error(f"Error propagating form elements in web map {webmap_id}: {str(e)}")
        progress_bar.empty()

def show_help():
    """Display help information for the Web Map Forms tool"""
    with st.expander("Need Help?"):
        st.markdown("""
        ### Web Map Forms Help
        
        #### Update Field
        The Update Field tab allows you to add or update a field in the form configuration of layers in a web map.
        
        - **Field Name**: The name of the field to add/update in forms
        - **Expression Name**: The name of the expression to use for the field value (e.g., "expr/set-project-number")
        - **Expression Value**: The value for the expression (random if not provided)
        - **Group Name**: The name of the group to add the field to (e.g., "Metadata")
        - **Field Label**: The label for the field (derived from field name if not provided)
        - **Editable**: Whether the field should be editable
        
        #### Propagate Forms
        The Propagate Forms tab allows you to copy form element configurations from a source layer to target layers.
        
        - **Source Layer**: The name of the source layer to copy configurations from
        - **Target Layers**: Optional list of target layer names (if not specified, all layers are considered)
        - **Fields**: Optional list of field names to propagate (if not specified, all matching fields are propagated)
        
        #### Debug Mode
        When Debug Mode is enabled, the tool will simulate updates without actually saving changes to the server.
        This is useful for testing and validation.
        
        #### Troubleshooting
        - Ensure your web map ID is correct
        - Verify that the source layer exists in the web map
        - Check that the target layers exist in the web map
        - Verify that the fields exist in the layers
        - Try running in Debug Mode to see more details
        """)
