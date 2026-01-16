"""
Shared field type validation for Web Map tools.
Validates values against Esri field types.
Supports both filter and form validation.
"""
import re
import json
import streamlit as st
from typing import Dict, List, Tuple, Any, Optional
from datetime import datetime

# Esri field type categories
NUMERIC_INTEGER_TYPES = ["esriFieldTypeInteger", "esriFieldTypeSmallInteger", "esriFieldTypeOID"]
NUMERIC_FLOAT_TYPES = ["esriFieldTypeDouble", "esriFieldTypeSingle"]
DATE_TYPES = ["esriFieldTypeDate"]
STRING_TYPES = ["esriFieldTypeString", "esriFieldTypeGUID", "esriFieldTypeGlobalID"]

# User-friendly field type names
FIELD_TYPE_DISPLAY_NAMES = {
    "esriFieldTypeInteger": "Integer",
    "esriFieldTypeSmallInteger": "Small Integer",
    "esriFieldTypeOID": "Object ID",
    "esriFieldTypeDouble": "Double",
    "esriFieldTypeSingle": "Float",
    "esriFieldTypeDate": "Date",
    "esriFieldTypeString": "Text",
    "esriFieldTypeGUID": "GUID",
    "esriFieldTypeGlobalID": "Global ID",
}

def get_field_type_display_name(field_type: str) -> str:
    """Get user-friendly display name for field type."""
    return FIELD_TYPE_DISPLAY_NAMES.get(field_type, field_type)


def validate_value_for_field_type(
    value: str, 
    field_type: str,
    operator: str = "="
) -> Tuple[bool, str]:
    """
    Validate a value against the expected field type.
    
    Args:
        value: The value to validate
        field_type: Esri field type (e.g., "esriFieldTypeInteger")
        operator: SQL operator being used (affects validation for IN, IS NULL, etc.)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    # NULL operators don't need value validation
    if operator in ["IS NULL", "IS NOT NULL"]:
        return (True, "")
    
    if not value:
        return (False, "Value is required")
    
    # Integer validation
    if field_type in NUMERIC_INTEGER_TYPES:
        return _validate_integer(value, operator)
    
    # Float validation
    if field_type in NUMERIC_FLOAT_TYPES:
        return _validate_numeric(value, operator)
    
    # Date validation
    if field_type in DATE_TYPES:
        return _validate_date(value, operator)
    
    # String types - no validation needed
    return (True, "")


def _validate_integer(value: str, operator: str) -> Tuple[bool, str]:
    """Validate integer value(s)."""
    values = [v.strip() for v in value.split(",")] if operator == "IN" else [value]
    
    for v in values:
        if not re.match(r'^-?\d+$', v):
            return (False, f"'{v}' is not a valid integer")
    return (True, "")


def _validate_numeric(value: str, operator: str) -> Tuple[bool, str]:
    """Validate numeric (float/double) value(s)."""
    values = [v.strip() for v in value.split(",")] if operator == "IN" else [value]
    
    for v in values:
        if not re.match(r'^-?\d+\.?\d*$', v):
            return (False, f"'{v}' is not a valid number")
    return (True, "")


def _validate_date(value: str, operator: str) -> Tuple[bool, str]:
    """Validate date value."""
    # Accept: YYYY-MM-DD, timestamps, or Arcade date()
    if value.startswith("date(") or value.startswith("timestamp"):
        return (True, "")
    
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return (True, "")
    except ValueError:
        pass
    
    # Try timestamp format
    try:
        int(value)
        return (True, "")
    except ValueError:
        pass
    
    return (False, f"'{value}' is not a valid date (use YYYY-MM-DD)")


def get_field_type_from_fields(
    field_name: str, 
    fields_with_types: List[Dict[str, str]]
) -> str:
    """Look up field type from fields_with_types list."""
    for field in fields_with_types:
        if field.get("name") == field_name:
            return field.get("type", "esriFieldTypeString")
    return "esriFieldTypeString"  # Default to string


def validate_form_value(
    value: str,
    field_type: str,
    field_name: str = ""
) -> Tuple[bool, str, List[str]]:
    """
    Validate a form default value against the expected field type.
    
    For forms, we need to validate that the value can be properly
    formatted as an Arcade expression.
    
    Args:
        value: The default value to validate
        field_type: Esri field type (e.g., "esriFieldTypeInteger")
        field_name: Field name for error messages
        
    Returns:
        Tuple of (is_valid, error_message, warnings)
    """
    warnings = []
    
    if not value:
        return (False, "Default value is required", warnings)
    
    # Validate based on field type
    if field_type in NUMERIC_INTEGER_TYPES:
        try:
            int(value)
        except ValueError:
            return (False, f"'{value}' is not a valid integer for field type {get_field_type_display_name(field_type)}", warnings)
    
    elif field_type in NUMERIC_FLOAT_TYPES:
        try:
            float(value)
        except ValueError:
            return (False, f"'{value}' is not a valid number for field type {get_field_type_display_name(field_type)}", warnings)
    
    elif field_type in DATE_TYPES:
        # Accept: YYYY-MM-DD, timestamps, or Date() function
        if value.startswith("Date(") or value.isdigit():
            pass
        else:
            try:
                datetime.strptime(value, "%Y-%m-%d")
            except ValueError:
                return (False, f"'{value}' is not a valid date. Use YYYY-MM-DD format or a timestamp.", warnings)
    
    # String types - check length warning
    elif field_type in STRING_TYPES:
        if len(value) > 255:
            warnings.append(f"Value length ({len(value)}) exceeds typical string field limit (255)")
    
    return (True, "", warnings)


def validate_form_has_form_info(has_form: bool, layer_name: str) -> Tuple[bool, str]:
    """
    Validate that a layer has form configuration.
    
    Args:
        has_form: Whether the layer has formInfo
        layer_name: Layer name for error messages
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not has_form:
        return (False, f"Layer '{layer_name}' does not have form configuration. Configure form in Map Viewer first.")
    return (True, "")


def show_validation_ui(
    edited_df,
    session_key: str,
    field_column: str = "Target Field",
    value_column: str = "Filter Value",
    operator_column: str = None,
    is_form_mode: bool = False
) -> bool:
    """
    Show validation button and results. Returns True if validation passed.
    
    Args:
        edited_df: DataFrame from AgGrid with edited data
        session_key: Unique key for session state (e.g., "filters", "forms")
        field_column: Column name containing field selection
        value_column: Column name containing the value
        operator_column: Optional column for SQL operator (for filters)
        is_form_mode: If True, use form-specific validation (default values instead of filters)
    
    Returns:
        True if validation passed and Apply should be enabled
    """
    validated_key = f"{session_key}_validated"
    results_key = f"{session_key}_validation_results"
    
    col1, col2 = st.columns([1, 3])
    with col1:
        validate_clicked = st.button("Validate", key=f"{session_key}_validate_btn")
    
    if validate_clicked:
        results = []
        all_valid = True
        
        for idx, row in edited_df.iterrows():
            if not row.get("Apply", False):
                continue
            
            layer_name = row.get("Layer Name", f"Row {idx}")
            field_name = row.get(field_column, "")
            value = str(row.get(value_column, "")).strip()
            operator = row.get(operator_column, "=") if operator_column else "="
            has_form = row.get("Has Form", True) if is_form_mode else True
            
            # Parse fields_with_types from JSON
            fields_json = row.get("_fields", "[]")
            try:
                fields = json.loads(fields_json) if isinstance(fields_json, str) else fields_json
            except (json.JSONDecodeError, TypeError):
                fields = []
            
            # Get field type
            field_type = get_field_type_from_fields(field_name, fields)
            field_type_display = get_field_type_display_name(field_type)
            
            warnings = []
            
            # Form-specific validations
            if is_form_mode:
                # Check if layer has form info
                form_valid, form_error = validate_form_has_form_info(has_form, layer_name)
                if not form_valid:
                    results.append({
                        "layer": layer_name,
                        "field": field_name,
                        "valid": False,
                        "error": form_error,
                        "type": field_type,
                        "type_display": field_type_display,
                        "warnings": []
                    })
                    all_valid = False
                    continue
                
                # Validate form value
                is_valid, error, warnings = validate_form_value(value, field_type, field_name)
            else:
                # Validate filter value
                is_valid, error = validate_value_for_field_type(value, field_type, operator)
            
            # Build preview string
            if is_form_mode:
                # Form expression preview
                preview = f'"{value}"' if field_type in STRING_TYPES else value
            else:
                # Filter preview
                if operator in ["IS NULL", "IS NOT NULL"]:
                    preview = f"{field_name} {operator}"
                elif operator == "IN":
                    preview = f"{field_name} IN ({value})"
                elif field_type in STRING_TYPES:
                    preview = f"{field_name} {operator} '{value}'"
                else:
                    preview = f"{field_name} {operator} {value}"
            
            results.append({
                "layer": layer_name,
                "field": field_name,
                "valid": is_valid,
                "error": error,
                "type": field_type,
                "type_display": field_type_display,
                "warnings": warnings,
                "value": value,
                "operator": operator,
                "preview": preview
            })
            
            if not is_valid:
                all_valid = False
        
        st.session_state[validated_key] = all_valid
        st.session_state[results_key] = results
    
    # Show results as table
    results = st.session_state.get(results_key, [])
    if results:
        _display_validation_table(results, is_form_mode)
    
    return st.session_state.get(validated_key, False)


def _display_validation_table(results: List[Dict], is_form_mode: bool = False) -> None:
    """
    Display validation results as a styled HTML table (fast, no pandas).
    
    Args:
        results: List of validation result dictionaries
        is_form_mode: Whether this is form validation (affects column header)
    """
    preview_header = "Expression" if is_form_mode else "Filter"
    
    # Build rows
    rows_html = ""
    for r in results:
        if r["valid"]:
            row_style = "background-color: #d4edda; color: #155724;"
            status = "OK"
        else:
            row_style = "background-color: #f8d7da; color: #721c24;"
            status = "Error"
        
        field_info = f"{_escape_html(r['field'])} ({r.get('type_display', '')})"
        preview = _escape_html(r.get("preview", ""))
        message = _escape_html(r.get("error", "")) if not r["valid"] else ""
        layer = _escape_html(r["layer"])
        
        rows_html += f'<tr style="{row_style}"><td><strong>{status}</strong></td><td>{layer}</td><td>{field_info}</td><td><code style="background:#f5f5f5;padding:2px 4px;border-radius:3px;">{preview}</code></td><td>{message}</td></tr>'
    
    # Build complete table
    html = f'<table style="width:100%;border-collapse:collapse;font-size:14px;"><tr style="background:#f0f2f6;"><th style="padding:8px;text-align:left;border-bottom:2px solid #ddd;width:60px;">Status</th><th style="padding:8px;text-align:left;border-bottom:2px solid #ddd;">Layer</th><th style="padding:8px;text-align:left;border-bottom:2px solid #ddd;">Field</th><th style="padding:8px;text-align:left;border-bottom:2px solid #ddd;">{preview_header}</th><th style="padding:8px;text-align:left;border-bottom:2px solid #ddd;">Message</th></tr>{rows_html}</table>'
    
    st.markdown("**Validation Results:**")
    st.markdown(html, unsafe_allow_html=True)
    
    # Show warnings separately if any
    warnings_found = False
    for r in results:
        if r.get("warnings"):
            if not warnings_found:
                st.markdown("**Warnings:**")
                warnings_found = True
            for warning in r["warnings"]:
                st.warning(f"{r['layer']}: {warning}")


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    if not text:
        return ""
    return (str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def show_form_validation_summary(validation_errors: List[str]) -> None:
    """
    Display form validation errors from the backend.
    
    Args:
        validation_errors: List of validation error messages from backend
    """
    if not validation_errors:
        return
    
    st.error(f"Form validation failed with {len(validation_errors)} error(s):")
    for error in validation_errors:
        st.markdown(f"- {error}")
