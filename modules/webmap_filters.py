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
logger = logging.getLogger("webmap_filters")

# Import the patch_webmap_filters module
try:
    from src import patch_webmap_filters
except ImportError:
    st.error("Failed to import patch_webmap_filters module. Make sure the src directory is in your Python path.")
    sys.exit(1)

def show():
    """Display the Web Map Filters interface"""
    # Check authentication first
    if not ensure_authentication():
        return
    
    # Show tool header
    show_tool_header(
        "Web Map Filters",
        "This tool allows you to update definition expressions (filters) in ArcGIS web maps. "
        "It will identify all layers containing a specific field and apply a new filter expression to them.",
        "🔍"
    )
    
    # Create tabs for different operations
    tab1, tab2 = st.tabs(["Update Filters", "Batch Operations"])
    
    with tab1:
        show_update_filters()
    
    with tab2:
        show_batch_operations()
    
    # Show help information
    show_help()

def show_update_filters():
    """Display the main filter update interface"""
    # Get GIS object
    gis = get_gis_object()
    if not gis:
        return
    
    # Web map selection using ItemSelector
    item_selector = ItemSelector(gis, "Web Map", "webmap_filters")
    selected_webmap = item_selector.show(
        title="Web Map Selection",
        help_text="Select the web map you want to update filters for.",
        default_id=st.session_state.get("webmap_id", "")
    )
    
    # Operation parameters
    parameters = [
        {
            "name": "target_field",
            "type": "text",
            "label": "Target Field",
            "help": "The field name to search for in layers",
            "default": "project_number",
            "placeholder": "Enter field name (e.g., project_number)",
            "required": True
        },
        {
            "name": "new_filter",
            "type": "textarea",
            "label": "New Filter Expression",
            "help": "The SQL expression to apply to matching layers",
            "default": "project_number = '123456'",
            "placeholder": "Enter SQL WHERE clause",
            "required": True
        }
    ]
    
    param_values = show_operation_parameters("Filter Parameters", parameters)
    
    # Debug mode control
    debug_mode = show_debug_mode_control("webmap_filters")
    
    # Validate inputs
    required_fields = ["target_field", "new_filter"]
    inputs = {
        "webmap_id": selected_webmap.id if selected_webmap else None,
        **param_values
    }
    
    is_valid, errors = validate_operation_inputs(inputs, required_fields + ["webmap_id"])
    
    # Execute button
    col1, col2 = st.columns([1, 3])
    with col1:
        update_button = st.button("Update Web Map Filters", type="primary", use_container_width=True)
    
    # Handle update request
    if update_button:
        if not is_valid:
            show_validation_errors(errors)
        else:
            # Execute the update
            execute_filter_update_with_status(
                inputs["webmap_id"],
                inputs["target_field"],
                inputs["new_filter"],
                debug_mode
            )

def show_batch_operations():
    """Display batch operations interface"""
    # Get batch item IDs
    webmap_ids = show_batch_operation_interface(
        "Filter Update",
        "web maps",
        "Enter web map IDs, one per line"
    )
    
    if webmap_ids:
        # Operation parameters
        parameters = [
            {
                "name": "target_field",
                "type": "text",
                "label": "Target Field",
                "help": "The field name to search for in layers",
                "default": "project_number",
                "placeholder": "Enter field name (e.g., project_number)",
                "required": True
            },
            {
                "name": "new_filter",
                "type": "textarea",
                "label": "New Filter Expression",
                "help": "The SQL expression to apply to matching layers",
                "default": "project_number = '123456'",
                "placeholder": "Enter SQL WHERE clause",
                "required": True
            }
        ]
        
        param_values = show_operation_parameters("Batch Parameters", parameters)
        
        # Debug mode control
        debug_mode = show_debug_mode_control("batch_webmap_filters")
        
        # Validate inputs
        required_fields = ["target_field", "new_filter"]
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
                execute_batch_filter_update_with_status(
                    webmap_ids,
                    param_values["target_field"],
                    param_values["new_filter"],
                    debug_mode
                )


def execute_filter_update_with_status(webmap_id: str, target_field: str, new_filter: str, debug_mode: bool) -> None:
    """Execute a filter update with consistent status display"""
    
    def update_operation(webmap_id: str, target_field: str, new_filter: str) -> List[str]:
        # Set debug mode
        patch_webmap_filters.DEBUG_MODE = debug_mode
        
        # Update the web map
        return patch_webmap_filters.update_webmap_definition_by_field(
            webmap_id, target_field, new_filter
        )
    
    # Execute with status display
    result = execute_operation_with_status(
        "Web Map Filter Update",
        update_operation,
        (webmap_id, target_field, new_filter),
        success_message=f"Successfully updated web map filters",
        error_message="Failed to update web map filters"
    )
    
    # Show results
    if result:
        def format_results(layers):
            return {
                "Layers Updated": len(layers),
                "Layer URLs": layers
            }
        
        show_operation_results(
            "Filter Update",
            result,
            success_criteria=lambda x: len(x) > 0,
            result_formatter=format_results
        )


def execute_batch_filter_update_with_status(webmap_ids: List[str], target_field: str, new_filter: str, debug_mode: bool) -> None:
    """Execute a batch filter update with consistent status display"""
    
    def batch_update_operation(webmap_ids: List[str], target_field: str, new_filter: str) -> Dict[str, Any]:
        # Set debug mode
        patch_webmap_filters.DEBUG_MODE = debug_mode
        
        results = {}
        successful_updates = 0
        failed_updates = 0
        total_layers_updated = 0
        
        for i, webmap_id in enumerate(webmap_ids):
            try:
                # Get the web map item
                webmap_item = patch_webmap_filters.get_webmap_item(webmap_id)
                
                if not webmap_item:
                    failed_updates += 1
                    results[webmap_id] = {"status": "error", "message": "Web map not found"}
                    continue
                
                # Update the web map
                updated_layers = patch_webmap_filters.update_webmap_definition_by_field(
                    webmap_id, target_field, new_filter
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
                    failed_updates += 1
                    results[webmap_id] = {
                        "status": "warning",
                        "title": webmap_item.title,
                        "message": "No layers were updated"
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
        "Batch Web Map Filter Update",
        batch_update_operation,
        (webmap_ids, target_field, new_filter),
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
            "Batch Filter Update",
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
                        st.success(f"**{webmap_result['title']}** ({webmap_id}): Updated {webmap_result['layers_updated']} layers")
                    elif status == "warning":
                        st.warning(f"**{webmap_result.get('title', 'Unknown')}** ({webmap_id}): {webmap_result['message']}")
                    else:
                        st.error(f"**Web Map** ({webmap_id}): {webmap_result['message']}")


def show_help():
    """Display help information for the Web Map Filters tool"""
    with st.expander("Need Help?"):
        st.markdown("""
        ### Web Map Filters Help
        
        #### Target Field
        The target field is the field name that the tool will look for in each layer.
        Only layers that contain this field will be updated.
        
        Common field names include:
        - `project_number` - Project identifier
        - `status` - Status field
        - `created_date` - Creation date
        
        #### Filter Expression
        The filter expression is an SQL WHERE clause that will be applied to matching layers.
        
        Examples:
        - `project_number = '123456'` - Exact match
        - `status IN ('Active', 'Pending')` - Multiple values
        - `created_date > '2023-01-01'` - Date comparison
        
        #### Debug Mode
        When Debug Mode is enabled, the tool will simulate updates without actually saving changes to the server.
        This is useful for testing and validation.
        
        #### Troubleshooting
        - Ensure your web map ID is correct
        - Verify that the target field exists in at least one layer
        - Check that your filter expression uses valid SQL syntax
        - Try running in Debug Mode to see more details
        """)
