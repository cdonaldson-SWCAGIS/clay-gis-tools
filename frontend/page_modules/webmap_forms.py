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
    ensure_authentication, get_gis_object, show_debug_mode_control,
    show_operation_parameters, validate_operation_inputs, show_validation_errors,
    execute_operation_with_status, show_operation_results, show_batch_operation_interface,
    create_help_section, show_tool_header, get_environment_setting
)
from backend.core.webmap.utils import (
    get_webmap_layer_details, 
    get_all_unique_fields, 
    get_webmap_item
)

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
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

# Configure logging
logger = logging.getLogger("webmap_forms")

# Import the webmap forms module
from backend.core.webmap import forms as patch_webmap_forms

def show():
    """Display the Web Map Forms interface"""
    # Check authentication first
    if not ensure_authentication():
        return
    
    # Show tool header
    show_tool_header(
        "Web Map Forms",
        "This tool allows you to update form configurations in ArcGIS web maps. "
        "It will identify all layers containing a specific field and apply form configuration changes to them.",
        ""
    )
    
    # Create tabs for different operations
    tab1, tab2, tab3 = st.tabs(["Update Forms", "Per-Layer Configuration", "Batch Operations"])
    
    with tab1:
        show_update_forms()
    
    with tab2:
        show_per_layer_config()
    
    with tab3:
        show_batch_operations()
    
    # Show help information
    show_help()

def show_update_forms():
    """Display the main form update interface"""
    # Get GIS object
    gis = get_gis_object()
    if not gis:
        return
    
    # Web map selection using ItemSelector
    item_selector = ItemSelector(gis, "Web Map", "webmap_forms")
    selected_webmap = item_selector.show(
        title="Web Map Selection",
        help_text="Select the web map you want to update forms for.",
        default_id=st.session_state.get("webmap_id", "")
    )
    
    # Operation parameters
    parameters = [
        {
            "name": "field_name",
            "type": "text",
            "label": "Field Name",
            "help": "The name of the field to add/update in forms",
            "default": "project_number",
            "placeholder": "Enter field name (e.g., project_number)",
            "required": True
        },
        {
            "name": "expression_name",
            "type": "text",
            "label": "Expression Name",
            "help": "The name of the expression to use for the field value",
            "default": "expr/set-project-number",
            "placeholder": "Enter expression name",
            "required": True
        },
        {
            "name": "expression_value",
            "type": "text",
            "label": "Expression Value (optional)",
            "help": "The value for the expression (random if not provided)",
            "default": "",
            "placeholder": "Enter expression value or leave blank for random"
        },
        {
            "name": "group_name",
            "type": "text",
            "label": "Group Name",
            "help": "The name of the group to add the field to",
            "default": "Metadata",
            "placeholder": "Enter group name",
            "required": True
        },
        {
            "name": "field_label",
            "type": "text",
            "label": "Field Label (optional)",
            "help": "The label for the field (derived from field name if not provided)",
            "default": "",
            "placeholder": "Enter field label or leave blank"
        },
        {
            "name": "editable",
            "type": "checkbox",
            "label": "Editable",
            "help": "Whether the field should be editable",
            "default": False
        }
    ]
    
    param_values = show_operation_parameters("Form Parameters", parameters)
    
    # Debug mode control
    debug_mode = show_debug_mode_control("webmap_forms")
    
    # Validate inputs
    required_fields = ["field_name", "expression_name", "group_name"]
    inputs = {
        "webmap_id": selected_webmap.id if selected_webmap else None,
        **param_values
    }
    
    is_valid, errors = validate_operation_inputs(inputs, required_fields + ["webmap_id"])
    
    # Operation mode selection (at the end, before execution)
    st.markdown("---")
    operation_mode = st.radio(
        "Apply Changes To",
        ["Update Webmap Layer(s)", "Save as New Webmap"],
        horizontal=True,
        help="Choose whether to update the existing webmap or create a new copy with these changes",
        key="update_forms_mode"
    )
    
    # If "Save as New Webmap", show title input
    new_title = None
    if operation_mode == "Save as New Webmap":
        map_suffix = get_environment_setting("MAP_SUFFIX", "_Copy")
        default_title = f"{selected_webmap.title}{map_suffix}" if selected_webmap else ""
        new_title = st.text_input(
            "New Web Map Title",
            value=default_title,
            help=f"Default: <Original Title>{map_suffix}. You can customize this title.",
            key="update_forms_new_title"
        )
        if not new_title:
            new_title = default_title
        if selected_webmap:
            st.info(f"**Preview:** The new web map will be titled: **{new_title}**")
    
    # Execute button
    col1, col2 = st.columns([1, 3])
    with col1:
        button_text = "Save as New Web Map" if operation_mode == "Save as New Webmap" else "Update Web Map Forms"
        update_button = st.button(button_text, type="primary", use_container_width=True)
    
    # Handle update request
    if update_button:
        if not is_valid:
            show_validation_errors(errors)
        else:
            # Execute the update or save as new
            if operation_mode == "Save as New Webmap":
                execute_form_update_as_new_with_status(
                    inputs["webmap_id"],
                    inputs["field_name"],
                    inputs["expression_name"],
                    inputs["expression_value"] or None,
                    inputs["group_name"],
                    inputs["field_label"] or None,
                    inputs["editable"],
                    new_title,
                    debug_mode
                )
            else:
                execute_form_update_with_status(
                    inputs["webmap_id"],
                    inputs["field_name"],
                    inputs["expression_name"],
                    inputs["expression_value"] or None,
                    inputs["group_name"],
                    inputs["field_label"] or None,
                    inputs["editable"],
                    debug_mode
                )

def show_per_layer_config():
    """Display per-layer form configuration interface with table editor"""
    # Get GIS object
    gis = get_gis_object()
    if not gis:
        return
    
    st.markdown("### Per-Layer Form Configuration")
    st.markdown("Configure form settings individually for each layer in your web map.")
    
    # Web map selection using ItemSelector
    item_selector = ItemSelector(gis, "Web Map", "webmap_forms_perlayer")
    selected_webmap = item_selector.show(
        title="Web Map Selection",
        help_text="Select the web map you want to configure forms for.",
        default_id=st.session_state.get("webmap_id", "")
    )
    
    if not selected_webmap:
        st.info("Please select a web map to view its layers.")
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
    
    # Get all unique fields across layers
    all_fields = get_all_unique_fields(layer_details)
    
    # Prepare DataFrame for the data editor
    df_data = []
    for layer in display_layers:
        df_data.append({
            "Apply": False,
            "Layer Name": layer["name"],
            "Has Form": layer.get("has_form_info", False),
            "Field Name": all_fields[0] if all_fields else "",
            "Expression Name": "expr/set-project-number",
            "Expression Value": "",
            "Group Name": "Metadata",
            "Label": "",
            "Editable": False,
            "_url": layer["url"],
            "_fields": layer["fields"]
        })
    
    df = pd.DataFrame(df_data)
    
    # Configure AgGrid columns
    st.markdown("#### Configure Layers")
    st.caption("Check 'Apply' for layers you want to update, then configure the form settings for each.")
    
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
        width=180,
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
    
    gb.configure_column(
        "Field Name",
        headerName="Field Name",
        editable=True,
        cellEditor="agSelectCellEditor",
        cellEditorParams={"values": all_fields if all_fields else [""]},
        width=140,
        headerTooltip="Field to configure in the form"
    )
    
    gb.configure_column(
        "Expression Name",
        headerName="Expression Name",
        editable=True,
        cellEditor="agTextCellEditor",
        width=170,
        headerTooltip="Name of the expression (e.g., expr/set-project-number)"
    )
    
    gb.configure_column(
        "Expression Value",
        headerName="Expression Value",
        editable=True,
        cellEditor="agTextCellEditor",
        width=140,
        headerTooltip="Value for the expression (leave blank for auto-generated)"
    )
    
    gb.configure_column(
        "Group Name",
        headerName="Group Name",
        editable=True,
        cellEditor="agTextCellEditor",
        width=110,
        headerTooltip="Form group to place the field in"
    )
    
    gb.configure_column(
        "Label",
        headerName="Label",
        editable=True,
        cellEditor="agTextCellEditor",
        width=100,
        headerTooltip="Display label for the field (auto-generated if blank)"
    )
    
    gb.configure_column(
        "Editable",
        headerName="Editable",
        editable=True,
        cellRenderer="agCheckboxCellRenderer",
        cellEditor="agCheckboxCellEditor",
        width=80,
        headerTooltip="Whether the field should be editable by users"
    )
    
    # Hide internal columns
    gb.configure_column("_url", hide=True)
    gb.configure_column("_fields", hide=True)
    
    grid_options = gb.build()
    
    # Display the AgGrid
    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        height=400,
        fit_columns_on_grid_load=True,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        data_return_mode=DataReturnMode.AS_INPUT,
        theme="streamlit",
        key=f"form_layer_editor_{selected_webmap.id}",
        allow_unsafe_jscode=True
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
        key="per_layer_config_mode"
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
            key="per_layer_config_new_title"
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
        # Build layer_configs from the edited dataframe
        layer_configs = {}
        validation_errors = []
        
        for idx, row in edited_df.iterrows():
            if row["Apply"]:
                layer_url = row["_url"]
                field_name = row["Field Name"]
                expression_name = row["Expression Name"]
                layer_name = row["Layer Name"]
                has_form = row["Has Form"]
                
                # Validate
                if not field_name:
                    validation_errors.append(f"'{layer_name}': Field name is required")
                    continue
                if not expression_name:
                    validation_errors.append(f"'{layer_name}': Expression name is required")
                    continue
                if not has_form:
                    validation_errors.append(f"'{layer_name}': Layer does not have form configuration")
                    continue
                
                # Check if field exists in this layer's fields
                layer_fields = row["_fields"]
                if field_name not in layer_fields:
                    validation_errors.append(f"'{layer_name}': Field '{field_name}' not available in this layer")
                    continue
                
                layer_configs[layer_url] = {
                    "field_name": field_name,
                    "expression_name": expression_name,
                    "expression_value": row["Expression Value"] or None,
                    "group_name": row["Group Name"] or "Metadata",
                    "field_label": row["Label"] or None,
                    "editable": row["Editable"]
                }
        
        if validation_errors:
            st.error("Validation errors:")
            for error in validation_errors:
                st.warning(f"- {error}")
        elif layer_configs:
            # Execute the per-layer update or save as new
            if operation_mode == "Save as New Webmap":
                execute_per_layer_form_update_as_new(
                    selected_webmap.id,
                    layer_configs,
                    gis,
                    new_title,
                    debug_mode
                )
            else:
                execute_per_layer_form_update(
                    selected_webmap.id,
                    layer_configs,
                    gis,
                    debug_mode
                )


def execute_per_layer_form_update_as_new(
    source_webmap_id: str,
    layer_configs: Dict[str, Dict[str, Any]],
    gis,
    new_title: str,
    debug_mode: bool
) -> None:
    """Execute a per-layer form update on a new webmap copy"""
    
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
                "expressions_added": [],
                "new_webmap_id": None,
                "new_webmap_title": new_title,
                "portal_url": None,
                "message": "DEBUG: Would create new webmap and apply forms"
            }
        
        # Then apply the form updates to the new webmap
        update_result = patch_webmap_forms.update_webmap_forms_by_layer_config(
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
    layer_configs: Dict[str, Dict[str, Any]],
    gis,
    debug_mode: bool
) -> None:
    """Execute a per-layer form update with status display"""
    
    def update_operation():
        return patch_webmap_forms.update_webmap_forms_by_layer_config(
            webmap_id, layer_configs, gis, debug_mode=debug_mode
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


def show_batch_operations():
    """Display batch operations interface"""
    # Get batch item IDs
    webmap_ids = show_batch_operation_interface(
        "Form Update",
        "web maps",
        "Enter web map IDs, one per line"
    )
    
    if webmap_ids:
        # Operation parameters
        parameters = [
            {
                "name": "field_name",
                "type": "text",
                "label": "Field Name",
                "help": "The name of the field to add/update in forms",
                "default": "project_number",
                "placeholder": "Enter field name (e.g., project_number)",
                "required": True
            },
            {
                "name": "expression_name",
                "type": "text",
                "label": "Expression Name",
                "help": "The name of the expression to use for the field value",
                "default": "expr/set-project-number",
                "placeholder": "Enter expression name",
                "required": True
            },
            {
                "name": "expression_value",
                "type": "text",
                "label": "Expression Value (optional)",
                "help": "The value for the expression (random if not provided)",
                "default": "",
                "placeholder": "Enter expression value or leave blank for random"
            },
            {
                "name": "group_name",
                "type": "text",
                "label": "Group Name",
                "help": "The name of the group to add the field to",
                "default": "Metadata",
                "placeholder": "Enter group name",
                "required": True
            },
            {
                "name": "field_label",
                "type": "text",
                "label": "Field Label (optional)",
                "help": "The label for the field (derived from field name if not provided)",
                "default": "",
                "placeholder": "Enter field label or leave blank"
            },
            {
                "name": "editable",
                "type": "checkbox",
                "label": "Editable",
                "help": "Whether the field should be editable",
                "default": False
            }
        ]
        
        param_values = show_operation_parameters("Batch Parameters", parameters)
        
        # Debug mode control
        debug_mode = show_debug_mode_control("batch_webmap_forms")
        
        # Validate inputs
        required_fields = ["field_name", "expression_name", "group_name"]
        is_valid, errors = validate_operation_inputs(param_values, required_fields)
        
        # Execute button
        col1, col2 = st.columns([1, 3])
        with col1:
            batch_button = st.button("Run Batch Update", type="primary", use_container_width=True)
        
        # Handle batch update request
        if batch_button:
            if not is_valid:
                show_validation_errors(errors)
            else:
                # Execute batch update
                execute_batch_form_update_with_status(
                    webmap_ids,
                    param_values["field_name"],
                    param_values["expression_name"],
                    param_values["expression_value"] or None,
                    param_values["group_name"],
                    param_values["field_label"] or None,
                    param_values["editable"],
                    debug_mode
                )


def execute_form_update_as_new_with_status(
    source_webmap_id: str,
    field_name: str,
    expression_name: str,
    expression_value: Optional[str],
    group_name: str,
    field_label: Optional[str],
    editable: bool,
    new_title: str,
    debug_mode: bool
) -> None:
    """Execute a form update on a new webmap copy with status display"""
    
    def save_and_update_operation():
        # First, create a copy of the webmap
        copy_result = copy_webmap_as_new(
            source_webmap_id,
            get_gis_object(),
            new_title=new_title,
            debug_mode=debug_mode
        )
        
        if not copy_result.get("success"):
            return {"success": False, "error": copy_result.get("message", "Failed to create webmap copy"), "layers": []}
        
        new_webmap_id = copy_result.get("new_webmap_id")
        if not new_webmap_id:
            # Debug mode - return simulated result
            return {
                "success": True,
                "layers": [],
                "new_webmap_id": None,
                "new_webmap_title": new_title,
                "portal_url": None,
                "message": "DEBUG: Would create new webmap and apply forms"
            }
        
        # Then apply the form updates to the new webmap
        updated_layers = patch_webmap_forms.update_webmap_forms(
            new_webmap_id, get_gis_object(), field_name, expression_name, expression_value,
            group_name, field_label, editable
        )
        
        return {
            "success": True,
            "layers": updated_layers,
            "new_webmap_id": new_webmap_id,
            "new_webmap_title": copy_result.get("new_webmap_title"),
            "portal_url": copy_result.get("portal_url"),
            "message": f"Successfully created new web map and updated forms"
        }
    
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
            layers_updated = len(result.get("layers", []))
            
            # Show new webmap info
            if result.get("new_webmap_id"):
                st.success(f"Successfully created new web map: {result.get('new_webmap_title', 'N/A')}")
                
                portal_url = result.get("portal_url")
                if portal_url:
                    st.markdown("---")
                    st.markdown("### Access Your New Web Map")
                    st.markdown(f"[**Open in Portal**]({portal_url})")
                    st.markdown(f"*Direct link: `{portal_url}`*")
            
            if layers_updated > 0:
                st.success(f"Successfully updated {layers_updated} layers in the new web map")
                if debug_mode:
                    st.info("Debug mode: Changes were simulated and not saved to the server")
            else:
                st.info("Form configuration added to the new web map")
        else:
            st.error(f"{result.get('error', 'Failed to create new web map with forms')}")


def execute_form_update_with_status(
    webmap_id: str,
    field_name: str,
    expression_name: str,
    expression_value: Optional[str],
    group_name: str,
    field_label: Optional[str],
    editable: bool,
    debug_mode: bool
) -> None:
    """Execute a form update with consistent status display"""
    
    def update_operation(webmap_id: str, field_name: str, expression_name: str, 
                        expression_value: Optional[str], group_name: str, 
                        field_label: Optional[str], editable: bool) -> List[str]:
        # Update the web map forms
        return patch_webmap_forms.update_webmap_forms(
            webmap_id, get_gis_object(), field_name, expression_name, expression_value,
            group_name, field_label, editable
        )
    
    # Execute with status display
    result = execute_operation_with_status(
        "Web Map Form Update",
        update_operation,
        (webmap_id, field_name, expression_name, expression_value, 
         group_name, field_label, editable),
        success_message=f"Successfully updated web map forms",
        error_message="Failed to update web map forms"
    )
    
    # Show results
    if result:
        def format_results(layers):
            return {
                "Layers Updated": len(layers),
                "Layer URLs": layers
            }
        
        show_operation_results(
            "Form Update",
            result,
            success_criteria=lambda x: len(x) > 0,
            result_formatter=format_results
        )


def execute_batch_form_update_with_status(
    webmap_ids: List[str],
    field_name: str,
    expression_name: str,
    expression_value: Optional[str],
    group_name: str,
    field_label: Optional[str],
    editable: bool,
    debug_mode: bool
) -> None:
    """Execute a batch form update with consistent status display"""
    
    def batch_update_operation(webmap_ids: List[str], field_name: str, expression_name: str,
                              expression_value: Optional[str], group_name: str,
                              field_label: Optional[str], editable: bool) -> Dict[str, Any]:
        # Set debug mode
        # Debug mode is now passed as a parameter to the function
        
        results = {}
        successful_updates = 0
        failed_updates = 0
        total_layers_updated = 0
        
        for i, webmap_id in enumerate(webmap_ids):
            try:
                # Get the web map item
                webmap_item = get_webmap_item(webmap_id, get_gis_object())
                
                if not webmap_item:
                    failed_updates += 1
                    results[webmap_id] = {"status": "error", "message": "Web map not found"}
                    continue
                
                # Update the web map forms
                updated_layers = patch_webmap_forms.update_webmap_forms(
                    webmap_id, get_gis_object(), field_name, expression_name, expression_value,
                    group_name, field_label, editable
                )
                
                # Record results
                if updated_layers:
                    successful_updates += 1
                    total_layers_updated += len(updated_layers)
                    results[webmap_id] = {
                        "status": "success",
                        "title": webmap_item.title,
                        "layers_updated": len(updated_layers),
                        "layer_urls": updated_layers
                    }
                else:
                    # Forms can still be updated even if no layers are returned
                    successful_updates += 1
                    results[webmap_id] = {
                        "status": "success",
                        "title": webmap_item.title,
                        "layers_updated": 0,
                        "message": "Expression info added to web map"
                    }
            
            except Exception as e:
                failed_updates += 1
                results[webmap_id] = {"status": "error", "message": str(e)}
                logger.error(f"Error processing web map {webmap_id} in batch update: {str(e)}")
        
        return {
            "results": results,
            "successful_updates": successful_updates,
            "failed_updates": failed_updates,
            "total_layers_updated": total_layers_updated,
            "total_webmaps": len(webmap_ids)
        }
    
    # Execute with status display
    result = execute_operation_with_status(
        "Batch Web Map Form Update",
        batch_update_operation,
        (webmap_ids, field_name, expression_name, expression_value,
         group_name, field_label, editable),
        success_message=f"Batch update completed",
        error_message="Batch update failed"
    )
    
    # Show results
    if result:
        def format_batch_results(batch_result):
            return {
                "Web Maps Processed": batch_result["total_webmaps"],
                "Successful Updates": batch_result["successful_updates"],
                "Failed Updates": batch_result["failed_updates"],
                "Total Layers Updated": batch_result["total_layers_updated"]
            }
        
        show_operation_results(
            "Batch Form Update",
            result,
            success_criteria=lambda x: x["successful_updates"] > 0,
            result_formatter=format_batch_results
        )
        
        # Show detailed results
        if result["results"]:
            with st.expander("Detailed Results", expanded=False):
                for webmap_id, webmap_result in result["results"].items():
                    status = webmap_result["status"]
                    if status == "success":
                        if webmap_result.get("layers_updated", 0) > 0:
                            st.success(f"**{webmap_result['title']}** ({webmap_id}): Updated {webmap_result['layers_updated']} layers")
                        else:
                            st.success(f"**{webmap_result['title']}** ({webmap_id}): {webmap_result.get('message', 'Updated successfully')}")
                    else:
                        st.error(f"**Web Map** ({webmap_id}): {webmap_result['message']}")

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
        # Update progress
        progress_bar.progress(25)
        status.info("Retrieving web map...")
        
        # Get the web map item
        webmap_item = get_webmap_item(webmap_id, get_gis_object())
        
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
            get_gis_object(),
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
        # Update progress
        progress_bar.progress(25)
        status.info("Retrieving web map...")
        
        # Get the web map item
        webmap_item = get_webmap_item(webmap_id, get_gis_object())
        
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
            get_gis_object(),
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

def show_save_as_new_simple(gis, key_prefix: str = "save_as_new"):
    """Display a simplified Save as New Web Map interface that can be embedded in other operations"""
    st.markdown("### Save as New Web Map")
    st.markdown("Create a copy of an existing web map with a new title. The new map will contain all layers and configurations from the source.")
    
    # Web map selection using ItemSelector
    item_selector = ItemSelector(gis, "Web Map", key_prefix)
    selected_webmap = item_selector.show(
        title="Source Web Map",
        help_text="Select the web map you want to copy.",
        default_id=st.session_state.get(f"{key_prefix}_webmap_id", "")
    )
    
    if not selected_webmap:
        st.info("Please select a web map to copy.")
        return
    
    # Store selected webmap ID in session state
    st.session_state[f"{key_prefix}_webmap_id"] = selected_webmap.id
    
    # Get MAP_SUFFIX from settings
    map_suffix = get_environment_setting("MAP_SUFFIX", "_Copy")
    
    # Title input with preview
    st.subheader("New Web Map Title")
    default_title = f"{selected_webmap.title}{map_suffix}"
    
    custom_title = st.text_input(
        "Title",
        value=default_title,
        help=f"Default: <Original Title>{map_suffix}. You can customize this title.",
        key=f"{key_prefix}_title"
    )
    
    if not custom_title:
        custom_title = default_title
    
    # Show preview
    st.info(f"**Preview:** The new web map will be titled: **{custom_title}**")
    
    # Debug mode control
    debug_mode = show_debug_mode_control(key_prefix)
    
    # Execute button
    col1, col2 = st.columns([1, 3])
    with col1:
        save_button = st.button("Save as New Web Map", type="primary", use_container_width=True, key=f"{key_prefix}_button")
    
    # Handle save request
    if save_button:
        execute_save_as_new(
            selected_webmap.id,
            custom_title,
            gis,
            debug_mode
        )


def show_save_as_new():
    """Display the Save as New Web Map interface (standalone version)"""
    gis = get_gis_object()
    if not gis:
        return
    show_save_as_new_simple(gis, "save_as_new")


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


def show_help():
    """Display help information for the Web Map Forms tool"""
    with st.expander("Need Help?"):
        st.markdown("""
        ### Web Map Forms Help
        
        #### Update Forms Tab
        Applies the same form configuration to all layers containing a specified field.
        
        - **Field Name**: The name of the field to add/update in forms
        - **Expression Name**: The expression to use for the field value (e.g., "expr/set-project-number")
        - **Expression Value**: The value for the expression (random if not provided)
        - **Group Name**: The form group to add the field to (e.g., "Metadata")
        - **Field Label**: Display label for the field (auto-generated if blank)
        - **Editable**: Whether the field should be editable by users
        
        #### Per-Layer Configuration Tab
        Configure form settings individually for each layer in your web map.
        
        1. Select a web map and click "Load Layers"
        2. Check the "Apply" box for layers you want to update
        3. Configure settings for each selected layer:
           - **Field Name**: Select from available fields
           - **Expression Name**: The expression to use
           - **Expression Value**: Optional value (auto-generated if blank)
           - **Group Name**: Form group to place the field in
           - **Label**: Display label
           - **Editable**: Whether users can edit this field
        4. Click "Update Selected Layers"
        
        **Note**: Only layers with existing form configuration can be updated. 
        Layers marked "Has Form = False" cannot have form settings applied.
        
        #### Batch Operations Tab
        Apply the same form configuration to multiple web maps at once.
        
        #### Save as New Webmap Option
        When you select "Save as New Webmap" as the operation mode, you can create a copy of an existing web map with a new title.
        
        - **Source Web Map**: Select the web map you want to copy
        - **Title**: Customize the title for the new web map (default: <Original Title>_<Suffix>)
        - The new map will contain all layers and configurations from the source
        - A link to the new web map will be provided after creation
        - Configure the default suffix in Settings → General → Map Suffix
        
        This option is available in both the "Update Forms" and "Per-Layer Configuration" tabs.
        
        #### Debug Mode
        When Debug Mode is enabled, the tool will simulate updates without actually saving changes to the server.
        This is useful for testing and validation.
        
        #### Troubleshooting
        - Ensure your web map ID is correct
        - Verify that layers have form configuration (Has Form = True)
        - Check that the field exists in the target layer
        - Try running in Debug Mode to see more details
        """)
