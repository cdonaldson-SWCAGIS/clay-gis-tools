import streamlit as st
import pandas as pd
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
from modules.webmap_utils import get_webmap_layer_details

# Configure logging
logger = logging.getLogger("webmap_filters")

# Import the patch_webmap_filters module
try:
    from src import patch_webmap_filters
except ImportError as e:
    st.error(f"Failed to import patch_webmap_filters module: {e}")
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
    tab1, tab2, tab3 = st.tabs(["Update Filters", "Per-Layer Configuration", "Batch Operations"])
    
    with tab1:
        show_update_filters()
    
    with tab2:
        show_per_layer_config()
    
    with tab3:
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

def get_field_type_display_name(field_type: str) -> str:
    """
    Convert ArcGIS field type to a user-friendly display name.
    
    Args:
        field_type: ArcGIS field type (e.g., 'esriFieldTypeString', 'esriFieldTypeDouble')
        
    Returns:
        User-friendly type name (e.g., 'Text', 'Double')
    """
    type_mapping = {
        "esriFieldTypeString": "Text",
        "esriFieldTypeInteger": "Integer",
        "esriFieldTypeSmallInteger": "Small Integer",
        "esriFieldTypeDouble": "Double",
        "esriFieldTypeSingle": "Single",
        "esriFieldTypeDate": "Date",
        "esriFieldTypeOID": "Object ID",
        "esriFieldTypeGUID": "GUID",
        "esriFieldTypeGlobalID": "Global ID",
        "esriFieldTypeBlob": "Blob",
        "esriFieldTypeRaster": "Raster",
        "esriFieldTypeGeometry": "Geometry",
        "esriFieldTypeXML": "XML"
    }
    # Remove 'esriFieldType' prefix and format nicely
    if field_type.startswith("esriFieldType"):
        base_type = field_type[13:]  # Remove 'esriFieldType' prefix
        return type_mapping.get(field_type, base_type)
    return type_mapping.get(field_type, field_type)


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
    
    st.markdown("### Per-Layer Filter Configuration")
    st.markdown("Configure filters individually for each layer in your web map.")
    
    # Web map selection using ItemSelector
    item_selector = ItemSelector(gis, "Web Map", "webmap_filters_perlayer")
    selected_webmap = item_selector.show(
        title="Web Map Selection",
        help_text="Select the web map you want to configure filters for.",
        default_id=st.session_state.get("webmap_id", "")
    )
    
    if not selected_webmap:
        st.info("Please select a web map to view its layers.")
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
    
    # Display layer and field information for easy copy/paste
    st.markdown("#### Layer and Field Reference")
    st.caption("Expand each layer to view its available fields grouped by type. Click on field names to copy them.")
    
    # Create expandable sections for each layer showing their fields grouped by type
    for layer in layer_details:
        layer_name = layer["name"]
        layer_path = layer["path"]
        fields_with_types = layer.get("fields_with_types", [])
        
        # Fallback to simple field names if types not available
        if not fields_with_types:
            fields = layer.get("fields", [])
            fields_with_types = [{"name": f, "type": "Unknown"} for f in fields]
        
        with st.expander(f"**{layer_name}** ({layer_path})", expanded=False):
            if fields_with_types:
                # Group fields by type
                fields_by_type = {}
                for field in fields_with_types:
                    field_type = field.get("type", "Unknown")
                    display_type = get_field_type_display_name(field_type)
                    if display_type not in fields_by_type:
                        fields_by_type[display_type] = []
                    fields_by_type[display_type].append(field["name"])
                
                # Sort types for consistent display
                sorted_types = sorted(fields_by_type.keys())
                
                st.markdown(f"**Available fields ({len(fields_with_types)} total):**")
                
                # Display fields grouped by type
                for field_type in sorted_types:
                    field_names = sorted(fields_by_type[field_type])
                    st.markdown(f"**{field_type}** ({len(field_names)} fields)")
                    
                    # Display all fields of this type in a selectable text block
                    fields_text = ", ".join(field_names)
                    st.code(fields_text, language=None)
                    
                    # Also display fields in a grid for visual reference
                    cols_per_row = 4
                    for i in range(0, len(field_names), cols_per_row):
                        cols = st.columns(cols_per_row)
                        for j, col in enumerate(cols):
                            if i + j < len(field_names):
                                field_name = field_names[i + j]
                                # Use code block for easy selection/copying
                                col.code(field_name, language=None)
                    
                    # Add spacing between type groups
                    if field_type != sorted_types[-1]:
                        st.markdown("")  # Empty line between groups
            else:
                st.info("No fields available for this layer.")
    
    st.divider()
    
    # Define filter operators
    filter_operators = ["=", "!=", ">", "<", ">=", "<=", "LIKE", "IN", "IS NULL", "IS NOT NULL"]
    
    # Prepare DataFrame for the data editor
    df_data = []
    for layer in layer_details:
        df_data.append({
            "Apply": False,
            "Layer Name": layer["name"],
            "Path": layer["path"],
            "Target Field": "",
            "Filter Operator": "=",
            "Filter Value": "",
            "_url": layer["url"],  # Hidden column for reference
            "_fields": layer["fields"]  # Store available fields per layer
        })
    
    df = pd.DataFrame(df_data)
    
    # Configure column settings for the data editor
    column_config = {
        "Apply": st.column_config.CheckboxColumn(
            "Apply",
            help="Check to apply filter to this layer",
            default=False
        ),
        "Layer Name": st.column_config.TextColumn(
            "Layer Name",
            help="Name of the layer in the web map",
            disabled=True
        ),
        "Path": st.column_config.TextColumn(
            "Path",
            help="Full path including group layers",
            disabled=True
        ),
        "Target Field": st.column_config.TextColumn(
            "Target Field",
            help="Field name to use in the filter expression (see Layer and Field Reference above for available fields)",
            required=True,
            width="medium"
        ),
        "Filter Operator": st.column_config.SelectboxColumn(
            "Filter Operator",
            help="SQL operator for the filter (e.g., =, !=, >, <, LIKE, IN)",
            options=filter_operators,
            required=True,
            default="="
        ),
        "Filter Value": st.column_config.TextColumn(
            "Filter Value",
            help="Value to filter by (e.g., '123456' for =, 'Active,Pending' for IN, '%ABC%' for LIKE). Leave empty for IS NULL/IS NOT NULL.",
            width="medium"
        ),
        "_url": None,  # Hide this column
        "_fields": None  # Hide this column
    }
    
    # Display the data editor
    st.markdown("#### Configure Layers")
    st.caption("Check 'Apply' for layers you want to update, then set the target field, operator, and value for each.")
    
    edited_df = st.data_editor(
        df,
        column_config=column_config,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        key=f"filter_layer_editor_{selected_webmap.id}"
    )
    
    # Debug mode control
    debug_mode = show_debug_mode_control("webmap_filters_perlayer")
    
    # Summary of selected layers
    selected_count = edited_df["Apply"].sum()
    st.markdown(f"**Selected layers:** {selected_count}")
    
    # Execute button
    col1, col2 = st.columns([1, 3])
    with col1:
        update_button = st.button(
            "Update Selected Layers",
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
                layer_fields = row["_fields"]
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
            # Execute the per-layer update
            execute_per_layer_filter_update(
                selected_webmap.id,
                layer_configs,
                gis,
                debug_mode
            )


def execute_per_layer_filter_update(
    webmap_id: str,
    layer_configs: Dict[str, Dict[str, str]],
    gis,
    debug_mode: bool
) -> None:
    """Execute a per-layer filter update with status display"""
    
    def update_operation():
        patch_webmap_filters.DEBUG_MODE = debug_mode
        return patch_webmap_filters.update_webmap_definitions_by_layer_config(
            webmap_id, layer_configs, gis, debug_mode
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
        
        #### Update Filters Tab
        Applies the same filter to all layers containing a specified field.
        
        - **Target Field**: The field name to search for in layers
        - **Filter Expression**: SQL WHERE clause to apply
        
        #### Per-Layer Configuration Tab
        Configure filters individually for each layer in your web map.
        
        1. Select a web map and click "Load Layers"
        2. Review the **Layer and Field Reference** section above to see available fields for each layer
        3. Expand a layer to view its fields - click on field names to copy them
        4. Check the "Apply" box for layers you want to update
        5. Enter the target field name (copy from the reference section above)
        6. Select the filter operator (e.g., =, !=, >, <, LIKE, IN, IS NULL)
        7. Enter the filter value (leave empty for IS NULL/IS NOT NULL)
        8. Click "Update Selected Layers"
        
        **Note**: Make sure the target field exists in the layer. If you enter a field that 
        doesn't exist in a particular layer, you'll receive a validation error.
        
        #### Filter Examples
        - **Equals (=)**: Operator `=`, Value `123456` → `project_number = '123456'`
        - **Not Equals (!=)**: Operator `!=`, Value `Active` → `status != 'Active'`
        - **Greater Than (>)**: Operator `>`, Value `2023-01-01` → `created_date > '2023-01-01'`
        - **LIKE**: Operator `LIKE`, Value `%ABC%` → `project_number LIKE '%ABC%'`
        - **IN**: Operator `IN`, Value `Active,Pending` → `status IN ('Active', 'Pending')`
        - **IS NULL**: Operator `IS NULL`, Value (empty) → `field_name IS NULL`
        
        #### Debug Mode
        When Debug Mode is enabled, the tool will simulate updates without actually saving changes to the server.
        This is useful for testing and validation.
        
        #### Troubleshooting
        - Ensure your web map ID is correct
        - Verify that the target field exists in at least one layer
        - Check that your filter expression uses valid SQL syntax
        - Try running in Debug Mode to see more details
        """)
