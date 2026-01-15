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
    execute_operation_with_status, show_tool_header
)
from backend.core.webmap.utils import get_webmap_layer_details

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
        "This tool allows you to configure definition expressions (filters) individually for each layer in your ArcGIS web maps.",
        "🔍"
    )
    
    # Show per-layer configuration interface
    show_per_layer_config()
    
    # Show help information
    show_help()

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
    st.markdown("#### Configure Layers")
    st.caption("Check 'Apply' for layers you want to update, then set the target field, operator, and value for each.")
    
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
    
    # Display the AgGrid
    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        height=400,
        fit_columns_on_grid_load=True,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        data_return_mode=DataReturnMode.AS_INPUT,
        theme="streamlit",
        key=f"filter_layer_editor_{selected_webmap.id}",
        allow_unsafe_jscode=True
    )
    
    # Get edited data from grid response
    edited_df = grid_response["data"]
    
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


def show_help():
    """Display help information for the Web Map Filters tool"""
    with st.expander("Need Help?"):
        st.markdown("""
        ### Web Map Filters Help
        
        #### Per-Layer Configuration
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
        - Verify that the target field exists in the layer you're trying to update
        - Check that your filter expression uses valid SQL syntax
        - Try running in Debug Mode to see more details
        """)
