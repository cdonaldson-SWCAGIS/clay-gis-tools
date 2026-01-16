import streamlit as st
import pandas as pd
import logging
import sys
import os
from typing import List, Optional, Dict, Any
import json

# Import utility modules
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from frontend.components.item_selector import ItemSelector, get_webmap_item
from frontend.components.common_operations import (
    ensure_authentication, get_gis_object, show_debug_mode_control,
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
logger = logging.getLogger("webmap_forms")

# Import the webmap forms module
from backend.core.webmap import forms as patch_webmap_forms


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
    """Display the Web Map Forms interface"""
    # Check authentication first
    if not ensure_authentication():
        return
    
    # Show tool header
    show_tool_header(
        "Web Map Forms",
        "Set default values for form fields across multiple layers. Select a field, enter a value, and apply to all selected layers.",
        ""
    )
    
    # Show per-layer configuration interface
    show_per_layer_config()
    
    # Show help information
    show_help()


def show_per_layer_config():
    """Display per-layer form configuration interface with table editor"""
    # Get GIS object
    gis = get_gis_object()
    if not gis:
        return
    
    st.markdown("### Set Default Values")
    st.markdown("Configure default form values for each layer. Different layers can use different field names.")
    
    # Web map selection using ItemSelector
    item_selector = ItemSelector(gis, "Web Map", "webmap_forms_perlayer")
    selected_webmap = item_selector.show(
        title="Web Map Selection",
        help_text="Select the web map you want to configure forms for.",
        default_id=st.session_state.get("webmap_id", "")
    )
    
    if not selected_webmap:
        return
    
    # Session state key for layer data
    layer_data_key = f"form_layer_data_{selected_webmap.id}"
    
    # Load layers button
    col1, col2 = st.columns([1, 3])
    with col1:
        load_layers = st.button("Load Layers", type="secondary", use_container_width=True, key="forms_load_layers")
    
    # Load or refresh layer data
    if load_layers or layer_data_key not in st.session_state:
        with st.spinner("Loading layer details..."):
            try:
                layer_details = get_webmap_layer_details(selected_webmap, gis)
                if layer_details:
                    # Filter to only layers with formInfo
                    layers_with_forms = [l for l in layer_details if l.get("has_form_info", False)]
                    st.session_state[layer_data_key] = layer_details
                    st.session_state[f"{layer_data_key}_with_forms"] = layers_with_forms
                    
                    if layers_with_forms:
                        st.success(f"Loaded {len(layer_details)} layers ({len(layers_with_forms)} with form configuration).")
                    else:
                        st.warning(f"Loaded {len(layer_details)} layers, but none have form configuration.")
                else:
                    st.warning("No feature layers found in this web map.")
                    return
            except Exception as e:
                st.error(f"Failed to load layers: {e}")
                logger.error(f"Error loading layer details: {e}")
                return
    
    # Get layer data from session state
    layer_details = st.session_state.get(layer_data_key, [])
    layers_with_forms = st.session_state.get(f"{layer_data_key}_with_forms", [])
    
    if not layer_details:
        st.info("Click 'Load Layers' to fetch the layer list.")
        return
    
    # Option to show all layers or just those with forms
    show_all = st.checkbox("Show all layers (including those without form configuration)", value=False)
    display_layers = layer_details if show_all else layers_with_forms
    
    if not display_layers:
        st.warning("No layers to display. Try checking 'Show all layers' above.")
        return
    
    # Prepare DataFrame for the data editor (simplified: only Apply, Layer Name, Field, Default Value)
    df_data = []
    for layer in display_layers:
        # Ensure fields is always a list (not None or other type)
        layer_fields = layer.get("fields", [])
        if not isinstance(layer_fields, list):
            layer_fields = []
        
        # Convert fields list to JSON string to ensure proper serialization
        fields_json = json.dumps(layer_fields) if layer_fields else "[]"
        
        df_data.append({
            "Apply": False,
            "Layer Name": layer["name"],
            "Has Form": layer.get("has_form_info", False),
            "Field": "",
            "Default Value": "",
            "_url": layer["url"],
            "_fields": fields_json  # Store as JSON string to ensure proper serialization
        })
    
    df = pd.DataFrame(df_data)
    
    # Configure AgGrid columns (simplified UI)
    st.markdown("#### Configure Layers")
    st.caption("Check 'Apply' for layers you want to update, select the field, and enter the default value.")
    
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
        width=70,
        headerTooltip="Check to apply form configuration to this layer"
    )
    
    gb.configure_column(
        "Layer Name",
        headerName="Layer Name",
        editable=False,
        width=200,
        headerTooltip="Name of the layer in the web map"
    )
    
    gb.configure_column(
        "Has Form",
        headerName="Has Form",
        editable=False,
        cellRenderer="agCheckboxCellRenderer",
        width=90,
        headerTooltip="Whether the layer has existing form configuration"
    )
    
    # Load the custom cell editor JavaScript from external file
    target_field_editor_js = load_js_file("static/js/dynamic_select_cell_editor.js")
    
    gb.configure_column(
        "Field",
        headerName="Field",
        editable=True,
        cellEditor=target_field_editor_js,
        width=180,
        headerTooltip="Field to set the default value for (dropdown shows available fields)"
    )
    
    gb.configure_column(
        "Default Value",
        headerName="Default Value",
        editable=True,
        cellEditor="agTextCellEditor",
        width=180,
        headerTooltip="The default value to set for this field when creating/editing features"
    )
    
    # Hide internal columns and configure them to avoid AgGrid warnings
    empty_formatter = JsCode("function(params) { return ''; }")
    
    gb.configure_column(
        "_url",
        hide=True,
        valueFormatter=empty_formatter,
        editable=False,
        sortable=False,
        filter=False,
        cellDataType=False
    )
    gb.configure_column(
        "_fields",
        hide=True,
        valueFormatter=empty_formatter,
        editable=False,
        sortable=False,
        filter=False,
        cellDataType=False
    )
    
    grid_options = gb.build()
    
    # Enable fill handle for range copy/paste
    grid_options["cellSelection"] = {
        "handle": {
            "mode": "fill",
            "direction": "y",
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
        key=f"form_layer_editor_{selected_webmap.id}",
        allow_unsafe_jscode=True,
        enable_enterprise_modules=True
    )
    
    # Get edited data from grid response
    edited_df = grid_response["data"]
    
    # Debug mode control
    debug_mode = show_debug_mode_control("webmap_forms_perlayer")
    
    # Summary of selected layers
    selected_count = edited_df["Apply"].sum()
    st.markdown(f"**Selected layers:** {selected_count}")
    
    # Operation mode selection (at the end, before execution)
    st.markdown("---")
    operation_mode = st.radio(
        "Apply Changes To",
        ["Update Webmap Layer(s)", "Save as New Webmap"],
        horizontal=True,
        help="Choose whether to update the existing webmap or create a new copy with these changes",
        key="forms_operation_mode"
    )
    
    # If "Save as New Webmap", show title input
    new_title = None
    if operation_mode == "Save as New Webmap":
        map_suffix = get_environment_setting("MAP_SUFFIX", "_Copy")
        default_title = f"{selected_webmap.title}{map_suffix}"
        new_title = st.text_input(
            "New Web Map Title",
            value=default_title,
            help=f"Default: <Original Title>{map_suffix}. You can customize this title.",
            key="forms_new_title"
        )
        if not new_title:
            new_title = default_title
        st.info(f"**Preview:** The new web map will be titled: **{new_title}**")
    
    # Execute button
    col1, col2 = st.columns([1, 3])
    with col1:
        button_text = "Save as New Web Map" if operation_mode == "Save as New Webmap" else "Update Selected Layers"
        update_button = st.button(
            button_text,
            type="primary",
            use_container_width=True,
            disabled=selected_count == 0,
            key="forms_update_btn"
        )
    
    # Handle update request
    if update_button and selected_count > 0:
        # Build layer_field_values from the edited dataframe (simplified format)
        layer_field_values = {}
        validation_errors = []
        
        for idx, row in edited_df.iterrows():
            if row["Apply"]:
                layer_url = row["_url"]
                field_name = row["Field"]
                default_value = str(row["Default Value"]).strip() if pd.notna(row["Default Value"]) else ""
                layer_name = row["Layer Name"]
                has_form = row["Has Form"]
                
                # Validate
                if not field_name:
                    validation_errors.append(f"'{layer_name}': Field is required")
                    continue
                if not default_value:
                    validation_errors.append(f"'{layer_name}': Default value is required")
                    continue
                if not has_form:
                    validation_errors.append(f"'{layer_name}': Layer does not have form configuration")
                    continue
                
                # Check if field exists in this layer's fields
                # Parse the JSON string back to a list
                layer_fields_str = row["_fields"]
                try:
                    if isinstance(layer_fields_str, str):
                        layer_fields = json.loads(layer_fields_str)
                    else:
                        layer_fields = layer_fields_str if isinstance(layer_fields_str, list) else []
                except (json.JSONDecodeError, TypeError):
                    layer_fields = []
                
                if field_name not in layer_fields:
                    validation_errors.append(f"'{layer_name}': Field '{field_name}' not available in this layer")
                    continue
                
                # Simplified format: just field_name and default_value
                layer_field_values[layer_url] = {
                    "field_name": field_name,
                    "default_value": default_value
                }
        
        if validation_errors:
            st.error("Validation errors:")
            for error in validation_errors:
                st.warning(f"- {error}")
        elif layer_field_values:
            # Execute the per-layer update or save as new using simplified function
            if operation_mode == "Save as New Webmap":
                execute_per_layer_form_update_as_new(
                    selected_webmap.id,
                    layer_field_values,
                    gis,
                    new_title,
                    debug_mode
                )
            else:
                execute_per_layer_form_update(
                    selected_webmap.id,
                    layer_field_values,
                    gis,
                    debug_mode
                )


def execute_per_layer_form_update_as_new(
    source_webmap_id: str,
    layer_field_values: Dict[str, Dict[str, str]],
    gis,
    new_title: str,
    debug_mode: bool
) -> None:
    """Execute a per-layer form update on a new webmap copy using simplified config."""
    
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
                "updated_layers": list(layer_field_values.keys()),
                "skipped_layers": [],
                "errors": {},
                "expressions_added": [],
                "new_webmap_id": None,
                "new_webmap_title": new_title,
                "portal_url": None,
                "message": "DEBUG: Would create new webmap and apply forms"
            }
        
        # Then apply the form updates to the new webmap using simplified function
        update_result = patch_webmap_forms.update_webmap_forms_simplified(
            new_webmap_id, gis, layer_field_values, debug_mode=debug_mode
        )
        
        # Combine results
        update_result["new_webmap_id"] = new_webmap_id
        update_result["new_webmap_title"] = copy_result.get("new_webmap_title")
        update_result["portal_url"] = copy_result.get("portal_url")
        update_result["success"] = True
        
        return update_result
    
    # Execute with status display
    result = execute_operation_with_status(
        "Save as New Web Map with Forms",
        save_and_update_operation,
        (),
        success_message="Successfully created new web map with forms",
        error_message="Failed to create new web map with forms"
    )
    
    # Show results
    if result:
        if result.get("success"):
            updated_count = len(result.get("updated_layers", []))
            skipped_count = len(result.get("skipped_layers", []))
            error_count = len(result.get("errors", {}))
            expressions_added = result.get("expressions_added", [])
            
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
            
            if expressions_added:
                st.info(f"Expressions added to web map: {', '.join(expressions_added)}")
            
            if updated_count > 0:
                st.success(f"Successfully updated {updated_count} layers in the new web map")
                if debug_mode:
                    st.info("Debug mode: Changes were simulated and not saved to the server")
            
            if result.get("errors"):
                with st.expander("Error Details", expanded=True):
                    for layer_url, error_msg in result["errors"].items():
                        st.error(f"{layer_url}: {error_msg}")
        else:
            st.error(f"{result.get('error', 'Failed to create new web map with forms')}")


def execute_per_layer_form_update(
    webmap_id: str,
    layer_field_values: Dict[str, Dict[str, str]],
    gis,
    debug_mode: bool
) -> None:
    """Execute a per-layer form update with status display using simplified config."""
    
    def update_operation():
        return patch_webmap_forms.update_webmap_forms_simplified(
            webmap_id, gis, layer_field_values, debug_mode=debug_mode
        )
    
    # Execute with status display
    result = execute_operation_with_status(
        "Per-Layer Form Update",
        lambda: update_operation(),
        (),
        success_message="Successfully updated web map forms",
        error_message="Failed to update web map forms"
    )
    
    # Show results
    if result:
        updated_count = len(result.get("updated_layers", []))
        skipped_count = len(result.get("skipped_layers", []))
        error_count = len(result.get("errors", {}))
        expressions_added = result.get("expressions_added", [])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Updated", updated_count)
        with col2:
            st.metric("Skipped", skipped_count)
        with col3:
            st.metric("Errors", error_count)
        
        if expressions_added:
            st.info(f"Expressions added to web map: {', '.join(expressions_added)}")
        
        if updated_count > 0:
            st.success(f"Successfully updated {updated_count} layers")
            if debug_mode:
                st.info("Debug mode: Changes were simulated and not saved to the server")
        
        if result.get("errors"):
            with st.expander("Error Details", expanded=True):
                for layer_url, error_msg in result["errors"].items():
                    st.error(f"{layer_url}: {error_msg}")


def show_help():
    """Display help information for the Web Map Forms tool"""
    with st.expander("Need Help?"):
        st.markdown("""
        ### Web Map Forms Help
        
        #### Setting Default Values for Form Fields
        This tool sets the default value that appears when users create or edit features.
        
        **Quick Start:**
        1. Select a web map and click "Load Layers"
        2. Check the "Apply" box for layers you want to update
        3. Select the **Field** for each layer (different layers can have different field names)
        4. Enter the **Default Value** for each layer
        5. Click "Update Selected Layers"
        
        #### Different Field Names Per Layer
        Some layers may have slightly different field names (e.g., `project_number` vs `parent_project_number`).
        The Field dropdown shows available fields for each layer, so you can select the correct one.
        
        #### Save as New Webmap Option
        Create a copy of the web map with the form changes applied:
        - Select "Save as New Webmap" before clicking update
        - Customize the title for the new web map
        - The original web map remains unchanged
        
        #### What Gets Auto-Generated
        The tool automatically generates these technical settings:
        - Expression name (from field name)
        - Display label (from field name)
        - Form group placement ("Metadata")
        
        #### Requirements
        - Only layers with existing form configuration can be updated (Has Form = True)
        - The field must exist in the layer's schema
        
        #### Debug Mode
        Enable Debug Mode to simulate updates without saving changes to the server.
        """)
