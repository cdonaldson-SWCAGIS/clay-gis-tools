import streamlit as st
import logging
import sys
import os
from typing import List, Optional, Dict, Any

# Import utility modules
from modules.item_utils import ItemSelector, get_webmap_item
from modules.common_operations import (
    ensure_authentication, get_gis_object, show_debug_mode_control,
    show_operation_parameters, validate_operation_inputs, show_validation_errors,
    execute_operation_with_status, show_operation_results, show_batch_operation_interface,
    create_help_section, show_tool_header
)

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
    # Check authentication first
    if not ensure_authentication():
        return
    
    # Show tool header
    show_tool_header(
        "Web Map Forms",
        "This tool allows you to update form configurations in ArcGIS web maps. "
        "It will identify all layers containing a specific field and apply form configuration changes to them.",
        "📝"
    )
    
    # Create tabs for different operations
    tab1, tab2 = st.tabs(["Update Forms", "Batch Operations"])
    
    with tab1:
        show_update_forms()
    
    with tab2:
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
    
    # Execute button
    col1, col2 = st.columns([1, 3])
    with col1:
        update_button = st.button("Update Web Map Forms", type="primary", use_container_width=True)
    
    # Handle update request
    if update_button:
        if not is_valid:
            show_validation_errors(errors)
        else:
            # Execute the update
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
        # Set debug mode
        patch_webmap_forms.DEBUG_MODE = debug_mode
        
        # Update the web map forms
        return patch_webmap_forms.update_webmap_forms(
            webmap_id, field_name, expression_name, expression_value,
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
        patch_webmap_forms.DEBUG_MODE = debug_mode
        
        results = {}
        successful_updates = 0
        failed_updates = 0
        total_layers_updated = 0
        
        for i, webmap_id in enumerate(webmap_ids):
            try:
                # Get the web map item
                webmap_item = patch_webmap_forms.get_webmap_item(webmap_id)
                
                if not webmap_item:
                    failed_updates += 1
                    results[webmap_id] = {"status": "error", "message": "Web map not found"}
                    continue
                
                # Update the web map forms
                updated_layers = patch_webmap_forms.update_webmap_forms(
                    webmap_id, field_name, expression_name, expression_value,
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
