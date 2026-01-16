import streamlit as st
import pandas as pd
import logging
import sys
import os
from typing import List, Optional, Dict, Any

# Import utility modules
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from frontend.components.item_selector import ItemSelector, get_webmap_item
from frontend.components.common_operations import (
    ensure_authentication, get_gis_object,
    execute_operation_with_status, show_tool_header, get_environment_setting
)
from backend.core.webmap.utils import get_webmap_layer_details

# Import copy_webmap_as_new with fallback
try:
    from backend.core.webmap.utils import copy_webmap_as_new
except ImportError:
    # Fallback: import directly if module cache issue
    import importlib
    import backend.core.webmap.utils as webmap_utils
    importlib.reload(webmap_utils)
    copy_webmap_as_new = webmap_utils.copy_webmap_as_new

# Import AgGrid components
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

# Configure logging
logger = logging.getLogger("webmap_filters")

# Import the webmap filters module
from backend.core.webmap import filters as patch_webmap_filters


def load_js_file(js_file_path: str) -> JsCode:
    """
    Load a JavaScript file and return it as a JsCode object for use with AgGrid.
    
    Args:
        js_file_path: Path to the JavaScript file relative to project root
        
    Returns:
        JsCode object containing the JavaScript code
    """
    project_root = Path(__file__).parent.parent.parent
    full_path = project_root / js_file_path
    
    if not full_path.exists():
        logger.error(f"JavaScript file not found: {full_path}")
        raise FileNotFoundError(f"JavaScript file not found: {full_path}")
    
    with open(full_path, 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    return JsCode(js_content)

def show():
    """Display the Web Map Filters interface"""
    # Check authentication first
    if not ensure_authentication():
        return
    
    # Show tool header
    show_tool_header(
        "Web Map Filters",
        "Configure definition expressions (filters) for web map layers."
    )
    
    # Show per-layer configuration interface
    show_per_layer_config()
    
    # Show help information
    show_help()

def build_filter_expression(field_name: str, operator: str, value: str) -> str:
    """
    Build a SQL filter expression from field name, operator, and value.
    
    Args:
        field_name: The field name to filter on
        operator: The SQL operator (=, !=, >, <, >=, <=, LIKE, IN, IS NULL, IS NOT NULL)
        value: The filter value (may be empty for NULL operators)
        
    Returns:
        A properly formatted SQL WHERE clause expression
    """
    # Handle NULL operators (don't need a value)
    if operator in ["IS NULL", "IS NOT NULL"]:
        return f"{field_name} {operator}"
    
    # Value is required for other operators
    if not value:
        return None
    
    # Handle IN operator (comma-separated values)
    if operator == "IN":
        # Split by comma and clean up values
        values = [v.strip() for v in value.split(",") if v.strip()]
        if not values:
            return None
        # Determine if values are numeric and quote accordingly
        formatted_values = []
        for v in values:
            try:
                # Try to parse as number
                float(v)
                # It's numeric, don't quote it
                formatted_values.append(v)
            except ValueError:
                # It's a string, quote it
                formatted_values.append(f"'{v}'")
        return f"{field_name} IN ({', '.join(formatted_values)})"
    
    # Handle LIKE operator (user may include wildcards)
    if operator == "LIKE":
        # Ensure value is quoted
        return f"{field_name} LIKE '{value}'"
    
    # Handle comparison operators (=, !=, >, <, >=, <=)
    # Try to determine if value is numeric
    try:
        # Try to parse as number
        float(value)
        # It's numeric, don't quote it
        return f"{field_name} {operator} {value}"
    except ValueError:
        # It's a string, quote it
        return f"{field_name} {operator} '{value}'"


def show_per_layer_config():
    """Display per-layer configuration interface with table editor"""
    # Get GIS object
    gis = get_gis_object()
    if not gis:
        return
    
    # Web map selection using ItemSelector
    item_selector = ItemSelector(gis, "Web Map", "webmap_filters_perlayer")
    selected_webmap = item_selector.show(
        title="Select Web Map",
        default_id=st.session_state.get("webmap_id", "")
    )
    
    if not selected_webmap:
        #st.info("Please select a web map to view its layers.")
        return
    
    # Session state key for layer data
    layer_data_key = f"layer_data_{selected_webmap.id}"
    
    # Load layers button
    col1, col2 = st.columns([1, 3])
    with col1:
        load_layers = st.button("Load Layers", type="secondary", use_container_width=True)
    
    # Load or refresh layer data
    if load_layers or layer_data_key not in st.session_state:
        with st.spinner("Loading layer details..."):
            try:
                layer_details = get_webmap_layer_details(selected_webmap, gis)
                if layer_details:
                    st.session_state[layer_data_key] = layer_details
                    st.success(f"Loaded {len(layer_details)} layers from the web map.")
                else:
                    st.warning("No feature layers found in this web map.")
                    return
            except Exception as e:
                st.error(f"Failed to load layers: {e}")
                logger.error(f"Error loading layer details: {e}")
                return
    
    # Get layer data from session state
    layer_details = st.session_state.get(layer_data_key, [])
    
    if not layer_details:
        st.info("Click 'Load Layers' to fetch the layer list.")
        return
    
    # Define filter operators
    filter_operators = ["=", "IN", "IS NOT NULL"]
    
    # Prepare DataFrame for the data editor
    import json
    df_data = []
    for layer in layer_details:
        # Ensure fields is always a list (not None or other type)
        layer_fields = layer.get("fields", [])
        if not isinstance(layer_fields, list):
            layer_fields = []
        
        # Convert fields list to JSON string to ensure proper serialization
        # This ensures the list is preserved when AgGrid serializes the data
        fields_json = json.dumps(layer_fields) if layer_fields else "[]"
        
        df_data.append({
            "Apply": False,
            "Layer Name": layer["name"],
            "Path": layer["path"],
            "Target Field": "",
            "Filter Operator": "=",
            "Filter Value": "",
            "_url": layer["url"],  # Hidden column for reference
            "_fields": fields_json  # Store as JSON string to ensure proper serialization
        })
    
    df = pd.DataFrame(df_data)
    
    # Configure AgGrid columns
    st.subheader("Layers")
    
    # Build grid options using GridOptionsBuilder
    gb = GridOptionsBuilder.from_dataframe(df)
    
    # Configure default column properties
    gb.configure_default_column(
        resizable=True,
        sortable=True,
        filter=True
    )
    
    # Configure individual columns
    gb.configure_column(
        "Apply",
        headerName="Apply",
        editable=True,
        cellRenderer="agCheckboxCellRenderer",
        cellEditor="agCheckboxCellEditor",
        width=80,
        headerTooltip="Check to apply filter to this layer"
    )
    
    gb.configure_column(
        "Layer Name",
        headerName="Layer Name",
        editable=False,
        width=200,
        headerTooltip="Name of the layer in the web map"
    )
    
    gb.configure_column(
        "Path",
        headerName="Path",
        editable=False,
        width=150,
        headerTooltip="Full path including group layers"
    )
    
    # Load the custom cell editor JavaScript from external file
    # This allows the JavaScript to be linted and maintained separately
    target_field_editor_js = load_js_file("static/js/dynamic_select_cell_editor.js")
    
    gb.configure_column(
        "Target Field",
        headerName="Target Field",
        editable=True,
        cellEditor=target_field_editor_js,
        width=150,
        headerTooltip="Field name to use in the filter expression (dropdown shows fields available for this layer)"
    )
    
    gb.configure_column(
        "Filter Operator",
        headerName="Filter Operator",
        editable=True,
        cellEditor="agSelectCellEditor",
        cellEditorParams={"values": filter_operators},
        width=130,
        headerTooltip="SQL operator for the filter"
    )
    
    gb.configure_column(
        "Filter Value",
        headerName="Filter Value",
        editable=True,
        cellEditor="agTextCellEditor",
        width=150,
        headerTooltip="Value to filter by. Leave empty for IS NULL/IS NOT NULL."
    )
    
    # Hide internal columns and configure them to avoid AgGrid warnings
    # These columns contain objects/arrays but are hidden
    # Disable cell data type inference to suppress warnings about object types
    empty_formatter = JsCode("function(params) { return ''; }")
    
    gb.configure_column(
        "_url",
        hide=True,
        valueFormatter=empty_formatter,
        editable=False,
        sortable=False,
        filter=False,
        cellDataType=False  # Disable type inference to suppress warnings
    )
    gb.configure_column(
        "_fields",
        hide=True,
        valueFormatter=empty_formatter,
        editable=False,
        sortable=False,
        filter=False,
        cellDataType=False  # Disable type inference to suppress warnings
    )
    
    grid_options = gb.build()
    
    # Enable fill handle for range copy/paste (Enterprise feature - adds watermark without license)
    grid_options["cellSelection"] = {
        "handle": {
            "mode": "fill",
            "direction": "y",  # Only allow vertical fill (down rows)
            "suppressClearOnFillReduction": True
        }
    }
    
    # Display the AgGrid with enterprise modules enabled for fill handle
    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        height=400,
        fit_columns_on_grid_load=True,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        data_return_mode=DataReturnMode.AS_INPUT,
        theme="streamlit",
        key=f"filter_layer_editor_{selected_webmap.id}",
        allow_unsafe_jscode=True,
        enable_enterprise_modules=True
    )
    
    # Get edited data from grid response
    edited_df = grid_response["data"]
    
    # Get debug mode from global settings
    debug_mode = st.session_state.get("debug_mode", True)
    
    # Summary of selected layers
    selected_count = edited_df["Apply"].sum()
    st.markdown(f"**Selected layers:** {selected_count}")
    
    # Operation mode selection
    st.divider()
    operation_mode = st.radio(
        "Save To",
        ["Update Existing", "Save as Copy"],
        horizontal=True,
        key="filters_operation_mode"
    )
    
    # If "Save as Copy", show title input
    new_title = None
    if operation_mode == "Save as Copy":
        map_suffix = get_environment_setting("MAP_SUFFIX", "_Copy")
        default_title = f"{selected_webmap.title}{map_suffix}"
        new_title = st.text_input(
            "New Title",
            value=default_title,
            key="filters_new_title"
        )
        if not new_title:
            new_title = default_title
    
    # Execute button
    col1, col2 = st.columns([1, 3])
    with col1:
        button_text = "Save Copy" if operation_mode == "Save as Copy" else "Apply Changes"
        update_button = st.button(
            button_text,
            type="primary",
            use_container_width=True,
            disabled=selected_count == 0
        )
    
    # Handle update request
    if update_button and selected_count > 0:
        # Build layer_configs from the edited dataframe
        layer_configs = {}
        validation_errors = []
        
        for idx, row in edited_df.iterrows():
            if row["Apply"]:
                layer_url = row["_url"]
                target_field = row["Target Field"]
                filter_operator = row["Filter Operator"]
                filter_value = str(row["Filter Value"]).strip() if pd.notna(row["Filter Value"]) else ""
                layer_name = row["Layer Name"]
                
                # Validate
                if not target_field:
                    validation_errors.append(f"'{layer_name}': Target field is required")
                    continue
                if not filter_operator:
                    validation_errors.append(f"'{layer_name}': Filter operator is required")
                    continue
                
                # Check if target field exists in this layer's fields
                # Parse the JSON string back to a list
                layer_fields_str = row["_fields"]
                try:
                    if isinstance(layer_fields_str, str):
                        layer_fields = json.loads(layer_fields_str)
                    else:
                        # If it's already a list (shouldn't happen, but handle it)
                        layer_fields = layer_fields_str if isinstance(layer_fields_str, list) else []
                except (json.JSONDecodeError, TypeError):
                    layer_fields = []
                
                if target_field not in layer_fields:
                    validation_errors.append(f"'{layer_name}': Field '{target_field}' not available in this layer")
                    continue
                
                # Build filter expression from components
                filter_expr = build_filter_expression(target_field, filter_operator, filter_value)
                if not filter_expr:
                    validation_errors.append(f"'{layer_name}': Invalid filter configuration (operator: {filter_operator}, value: {filter_value})")
                    continue
                
                layer_configs[layer_url] = {
                    "target_field": target_field,
                    "filter_expression": filter_expr
                }
        
        if validation_errors:
            st.error("Validation errors:")
            for error in validation_errors:
                st.warning(f"- {error}")
        elif layer_configs:
            # Execute the per-layer update or save as new
            if operation_mode == "Save as Copy":
                execute_per_layer_filter_update_as_new(
                    selected_webmap.id,
                    layer_configs,
                    gis,
                    new_title,
                    debug_mode
                )
            else:
                execute_per_layer_filter_update(
                    selected_webmap.id,
                    layer_configs,
                    gis,
                    debug_mode
                )


def execute_per_layer_filter_update_as_new(
    source_webmap_id: str,
    layer_configs: Dict[str, Dict[str, str]],
    gis,
    new_title: str,
    debug_mode: bool
) -> None:
    """Execute a per-layer filter update on a new webmap copy"""
    
    def save_and_update_operation():
        # First, create a copy of the webmap
        copy_result = copy_webmap_as_new(
            source_webmap_id,
            gis,
            new_title=new_title,
            debug_mode=debug_mode
        )
        
        if not copy_result.get("success"):
            return {"success": False, "error": copy_result.get("message", "Failed to create webmap copy")}
        
        new_webmap_id = copy_result.get("new_webmap_id")
        if not new_webmap_id:
            # Debug mode - return simulated result
            return {
                "success": True,
                "updated_layers": list(layer_configs.keys()),
                "skipped_layers": [],
                "errors": {},
                "new_webmap_id": None,
                "new_webmap_title": new_title,
                "portal_url": None,
                "message": "DEBUG: Would create new webmap and apply filters"
            }
        
        # Then apply the filter updates to the new webmap
        update_result = patch_webmap_filters.update_webmap_definitions_by_layer_config(
            new_webmap_id, layer_configs, gis, debug_mode=debug_mode
        )
        
        # Combine results
        update_result["new_webmap_id"] = new_webmap_id
        update_result["new_webmap_title"] = copy_result.get("new_webmap_title")
        update_result["portal_url"] = copy_result.get("portal_url")
        update_result["success"] = True
        
        return update_result
    
    # Execute with status display
    result = execute_operation_with_status(
        "Save as New Web Map with Filters",
        save_and_update_operation,
        (),
        success_message="Successfully created new web map with filters",
        error_message="Failed to create new web map with filters"
    )
    
    # Show results
    if result:
        if result.get("success"):
            updated_count = len(result.get("updated_layers", []))
            skipped_count = len(result.get("skipped_layers", []))
            error_count = len(result.get("errors", {}))
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Updated", updated_count)
            with col2:
                st.metric("Skipped", skipped_count)
            with col3:
                st.metric("Errors", error_count)
            
            # Show new webmap info
            if result.get("new_webmap_id"):
                st.success(f"Successfully created new web map: {result.get('new_webmap_title', 'N/A')}")
                
                portal_url = result.get("portal_url")
                if portal_url:
                    st.markdown("---")
                    st.markdown("### Access Your New Web Map")
                    st.markdown(f"[**Open in Portal**]({portal_url})")
                    st.markdown(f"*Direct link: `{portal_url}`*")
            
            if updated_count > 0:
                st.success(f"Successfully updated {updated_count} layers in the new web map")
                if debug_mode:
                    st.info("Debug mode: Changes were simulated and not saved to the server")
            
            if result.get("errors"):
                with st.expander("Error Details", expanded=True):
                    for layer_url, error_msg in result["errors"].items():
                        st.error(f"{layer_url}: {error_msg}")
        else:
            st.error(f"{result.get('error', 'Failed to create new web map with filters')}")


def execute_per_layer_filter_update(
    webmap_id: str,
    layer_configs: Dict[str, Dict[str, str]],
    gis,
    debug_mode: bool
) -> None:
    """Execute a per-layer filter update with status display"""
    
    def update_operation():
        return patch_webmap_filters.update_webmap_definitions_by_layer_config(
            webmap_id, layer_configs, gis, debug_mode=debug_mode
        )
    
    # Execute with status display
    result = execute_operation_with_status(
        "Per-Layer Filter Update",
        lambda: update_operation(),
        (),
        success_message="Successfully updated web map filters",
        error_message="Failed to update web map filters"
    )
    
    # Show results
    if result:
        updated_count = len(result.get("updated_layers", []))
        skipped_count = len(result.get("skipped_layers", []))
        error_count = len(result.get("errors", {}))
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Updated", updated_count)
        with col2:
            st.metric("Skipped", skipped_count)
        with col3:
            st.metric("Errors", error_count)
        
        if updated_count > 0:
            st.success(f"Successfully updated {updated_count} layers")
            if debug_mode:
                st.info("Debug mode: Changes were simulated and not saved to the server")
        
        if result.get("errors"):
            with st.expander("Error Details", expanded=True):
                for layer_url, error_msg in result["errors"].items():
                    st.error(f"{layer_url}: {error_msg}")


def show_save_as_new():
    """Display the Save as New Web Map interface"""
    # Get GIS object
    gis = get_gis_object()
    if not gis:
        return
    
    st.markdown("### Save as New Web Map")
    st.markdown("Create a copy of an existing web map with a new title. The new map will contain all layers and configurations from the source.")
    
    # Web map selection using ItemSelector
    item_selector = ItemSelector(gis, "Web Map", "save_as_new_filters")
    selected_webmap = item_selector.show(
        title="Source Web Map",
        help_text="Select the web map you want to copy.",
        default_id=st.session_state.get("save_as_new_webmap_id_filters", "")
    )
    
    if not selected_webmap:
        st.info("Please select a web map to copy.")
        return
    
    # Store selected webmap ID in session state
    st.session_state.save_as_new_webmap_id_filters = selected_webmap.id
    
    # Get MAP_SUFFIX from settings
    map_suffix = get_environment_setting("MAP_SUFFIX", "_Copy")
    
    # Title input with preview
    st.subheader("New Web Map Title")
    default_title = f"{selected_webmap.title}{map_suffix}"
    
    custom_title = st.text_input(
        "Title",
        value=default_title,
        help=f"Default: <Original Title>{map_suffix}. You can customize this title.",
        key="save_as_new_title_filters"
    )
    
    if not custom_title:
        custom_title = default_title
    
    # Show preview
    st.info(f"**Preview:** The new web map will be titled: **{custom_title}**")
    
    # Get debug mode from global settings
    debug_mode = st.session_state.get("debug_mode", True)
    
    # Execute button
    col1, col2 = st.columns([1, 3])
    with col1:
        save_button = st.button("Save as New Web Map", type="primary", use_container_width=True)
    
    # Handle save request
    if save_button:
        execute_save_as_new(
            selected_webmap.id,
            custom_title,
            gis,
            debug_mode
        )


def execute_save_as_new(
    webmap_id: str,
    new_title: str,
    gis,
    debug_mode: bool
) -> None:
    """Execute the Save as New operation with status display"""
    
    def save_operation():
        return copy_webmap_as_new(
            webmap_id,
            gis,
            new_title=new_title,
            debug_mode=debug_mode
        )
    
    # Execute with status display
    result = execute_operation_with_status(
        "Save as New Web Map",
        save_operation,
        (),
        success_message="Successfully created new web map",
        error_message="Failed to create new web map"
    )
    
    # Show results
    if result:
        if result.get("success"):
            st.success(f"{result.get('message', 'Successfully created new web map')}")
            
            # Display new web map details
            col1, col2 = st.columns(2)
            with col1:
                st.metric("New Web Map Title", result.get("new_webmap_title", "N/A"))
            with col2:
                if result.get("new_webmap_id"):
                    st.metric("New Web Map ID", result.get("new_webmap_id", "N/A"))
            
            # Show portal link if available
            portal_url = result.get("portal_url")
            if portal_url:
                st.markdown("---")
                st.markdown("### Access Your New Web Map")
                st.markdown(f"[**Open in Portal**]({portal_url})")
                st.markdown(f"*Direct link: `{portal_url}`*")
            elif debug_mode:
                st.info("Debug Mode: Portal link will be available when running in production mode")
            
            if debug_mode:
                st.info("**Debug Mode**: The web map was not actually created. Disable debug mode to create the map.")
        else:
            st.error(f"{result.get('message', 'Failed to create new web map')}")
            
            # Show troubleshooting tips
            with st.expander("Troubleshooting", expanded=False):
                st.markdown("""
                **Common issues:**
                - Ensure you have permission to read the source web map
                - Verify you have permission to create new web maps
                - Check that the web map ID is correct
                - Try running in Debug Mode to see more details
                """)


def load_help_markdown(filename: str) -> str:
    """Load help markdown from docs folder."""
    docs_path = Path(__file__).parent.parent.parent / "docs" / filename
    try:
        with open(docs_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return "Help content not available."


def show_help():
    """Display help information for the Web Map Filters tool"""
    with st.expander("Help"):
        st.markdown(load_help_markdown("help_webmap_filters.md"))
