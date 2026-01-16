import json
import logging
import os
import random
import string
from typing import List, Optional, Dict, Any, Union, Tuple

from arcgis.features import FeatureLayer
from arcgis.gis import GIS

from backend.utils.logging import get_logger
from backend.core.webmap.utils import (
    get_webmap_item, layer_contains_field, process_webmap_layers, get_layer_item_form_info
)
from backend.utils.exceptions import (
    WebMapNotFoundError, InvalidWebMapError, LayerProcessingError, AuthenticationError
)
from backend.utils.config import (
    OPERATIONAL_LAYERS_KEY, FORM_INFO_KEY, FORM_ELEMENTS_KEY,
    EXPRESSION_INFOS_KEY, URL_KEY, TITLE_KEY, LAYERS_KEY, UNNAMED_LAYER,
    DEFAULT_GROUP_NAME, EXPR_SYSTEM_FALSE, EXPR_SYSTEM_TRUE
)

logger = get_logger("patch_webmap_forms")

# Global debug mode: Set to True to simulate updates (for testing) or False for production.
DEBUG_MODE = False

def generate_random_string(length: int = 8) -> str:
    """Generate a random alphanumeric string of specified length."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# get_webmap_item and layer_contains_field are now imported from modules.webmap_utils

def has_expression_info(webmap_data: Dict, expression_name: str) -> bool:
    """Check if the web map already has the specified expression info."""
    if "expressionInfos" not in webmap_data:
        return False
    
    return any(expr.get("name") == expression_name for expr in webmap_data["expressionInfos"])


def update_expression_value(
    webmap_data: Dict, 
    expression_name: str, 
    expression_value: str,
    field_type: Optional[str] = None
) -> bool:
    """
    Update the value of an existing expression in the web map's expressionInfos.
    
    Args:
        webmap_data: The web map data dictionary
        expression_name: The name of the expression to update
        expression_value: The new value for the expression
        field_type: Optional Esri field type to format the value correctly
        
    Returns:
        bool: True if the expression was updated, False if not found or unchanged
    """
    if "expressionInfos" not in webmap_data:
        return False
    
    # Format the expression value based on field type
    if field_type:
        numeric_types = ["esriFieldTypeInteger", "esriFieldTypeSmallInteger", 
                        "esriFieldTypeOID", "esriFieldTypeDouble", "esriFieldTypeSingle"]
        date_types = ["esriFieldTypeDate"]
        
        if field_type in numeric_types:
            try:
                float(expression_value)
                formatted_expression = expression_value
            except ValueError:
                formatted_expression = f'"{expression_value}"'
        elif field_type in date_types:
            if expression_value.startswith("Date(") or expression_value.isdigit():
                formatted_expression = expression_value
            else:
                try:
                    from datetime import datetime
                    dt = datetime.strptime(expression_value, "%Y-%m-%d")
                    timestamp = int(dt.timestamp() * 1000)
                    formatted_expression = str(timestamp)
                except ValueError:
                    formatted_expression = f'"{expression_value}"'
        else:
            formatted_expression = f'"{expression_value}"'
    else:
        formatted_expression = f'"{expression_value}"'
    
    # Find and update the expression
    for expr in webmap_data["expressionInfos"]:
        if expr.get("name") == expression_name:
            old_value = expr.get("expression")
            if old_value != formatted_expression:
                expr["expression"] = formatted_expression
                logger.info(f"Updated expression '{expression_name}' value from '{old_value}' to '{formatted_expression}'")
                return True
            else:
                logger.debug(f"Expression '{expression_name}' already has value '{formatted_expression}'")
                return False
    
    logger.warning(f"Expression '{expression_name}' not found for update")
    return False


def ensure_expression_infos(webmap_data: Dict) -> None:
    """Ensure that expressionInfos exists in the web map data."""
    if "expressionInfos" not in webmap_data:
        webmap_data["expressionInfos"] = []

def add_custom_expression(
    webmap_data: Dict, 
    expression_name: str, 
    expression_value: Optional[str] = None, 
    title: Optional[str] = None, 
    return_type: str = "string",
    field_type: Optional[str] = None,
    update_if_exists: bool = False
) -> bool:
    """
    Add a custom expression to the web map's expressionInfos.
    
    Args:
        webmap_data: The web map data dictionary
        expression_name: The name of the expression (e.g., "expr/set-project-number")
        expression_value: The value for the expression (random if not provided)
        title: The title for the expression (derived from name if not provided)
        return_type: The return type of the expression (default: "string")
                     Will be overridden by field_type if provided.
        field_type: Optional Esri field type (e.g., "esriFieldTypeInteger").
                    If provided, overrides return_type and formats value correctly.
        update_if_exists: If True, update the expression value if it already exists.
        
    Returns:
        bool: True if the expression was added or updated, False if it already existed unchanged
    """
    ensure_expression_infos(webmap_data)
    
    # Check if the expression already exists
    if has_expression_info(webmap_data, expression_name):
        if update_if_exists and expression_value is not None:
            # Update the existing expression
            return update_expression_value(webmap_data, expression_name, expression_value, field_type)
        logger.info(f"Expression '{expression_name}' already exists")
        return False
    
    # Add the system/false expression if it doesn't exist
    if not has_expression_info(webmap_data, "expr/system/false"):
        webmap_data["expressionInfos"].append({
            "expression": "false",
            "name": "expr/system/false",
            "returnType": "boolean",
            "title": "False"
        })
        logger.info("Added system/false expression")
    
    # Add the system/true expression if it doesn't exist
    if not has_expression_info(webmap_data, "expr/system/true"):
        webmap_data["expressionInfos"].append({
            "expression": "true",
            "name": "expr/system/true",
            "returnType": "boolean",
            "title": "True"
        })
        logger.info("Added system/true expression")
    
    # Generate a value if not provided
    if expression_value is None:
        expression_value = generate_random_string(6)
    
    # Generate a title if not provided
    if title is None:
        # Convert expr/set-project-number to "Set Project Number"
        parts = expression_name.split('/')
        base_name = parts[-1] if len(parts) > 0 else expression_name
        title = ' '.join(word.capitalize() for word in base_name.replace('-', ' ').split())
    
    # Determine return type and format expression value based on field type
    if field_type:
        # Field type to return type mapping (defined later in validation section)
        field_type_to_return = {
            "esriFieldTypeString": "string",
            "esriFieldTypeGUID": "string",
            "esriFieldTypeGlobalID": "string",
            "esriFieldTypeInteger": "number",
            "esriFieldTypeSmallInteger": "number",
            "esriFieldTypeOID": "number",
            "esriFieldTypeDouble": "number",
            "esriFieldTypeSingle": "number",
            "esriFieldTypeDate": "date",
        }
        return_type = field_type_to_return.get(field_type, "string")
        
        # Format expression value based on field type
        numeric_types = ["esriFieldTypeInteger", "esriFieldTypeSmallInteger", 
                        "esriFieldTypeOID", "esriFieldTypeDouble", "esriFieldTypeSingle"]
        date_types = ["esriFieldTypeDate"]
        
        if field_type in numeric_types:
            # Numbers should not be quoted
            try:
                float(expression_value)
                formatted_expression = expression_value
            except ValueError:
                logger.warning(f"Value '{expression_value}' is not a valid number for field type {field_type}")
                formatted_expression = f'"{expression_value}"'
        elif field_type in date_types:
            # Dates: use timestamp or Date() function
            if expression_value.startswith("Date(") or expression_value.isdigit():
                formatted_expression = expression_value
            else:
                try:
                    from datetime import datetime
                    dt = datetime.strptime(expression_value, "%Y-%m-%d")
                    timestamp = int(dt.timestamp() * 1000)
                    formatted_expression = str(timestamp)
                except ValueError:
                    logger.warning(f"Value '{expression_value}' could not be parsed as date")
                    formatted_expression = f'"{expression_value}"'
        else:
            # Strings should be quoted
            formatted_expression = f'"{expression_value}"'
    else:
        # Default: wrap in quotes for string type
        formatted_expression = f'"{expression_value}"'
    
    # Add the custom expression
    webmap_data["expressionInfos"].append({
        "expression": formatted_expression,
        "name": expression_name,
        "returnType": return_type,
        "title": title
    })
    logger.info(f"Added expression '{expression_name}' with value: {expression_value} (type: {return_type})")
    
    return True


# =============================================================================
# Form Validation Functions
# =============================================================================

# Esri field type to expression return type mapping
ESRI_FIELD_TYPE_TO_RETURN_TYPE = {
    "esriFieldTypeString": "string",
    "esriFieldTypeGUID": "string",
    "esriFieldTypeGlobalID": "string",
    "esriFieldTypeInteger": "number",
    "esriFieldTypeSmallInteger": "number",
    "esriFieldTypeOID": "number",
    "esriFieldTypeDouble": "number",
    "esriFieldTypeSingle": "number",
    "esriFieldTypeDate": "date",
}

# Field types that should have numeric expression values (no quotes)
NUMERIC_FIELD_TYPES = ["esriFieldTypeInteger", "esriFieldTypeSmallInteger", 
                       "esriFieldTypeOID", "esriFieldTypeDouble", "esriFieldTypeSingle"]

# Field types that should have date expression values
DATE_FIELD_TYPES = ["esriFieldTypeDate"]


def get_expression_return_type(field_type: str) -> str:
    """
    Get the correct expression returnType for a given Esri field type.
    
    Args:
        field_type: Esri field type (e.g., "esriFieldTypeInteger")
        
    Returns:
        Expression return type ("string", "number", or "date")
    """
    return ESRI_FIELD_TYPE_TO_RETURN_TYPE.get(field_type, "string")


def format_expression_value(value: str, field_type: str) -> str:
    """
    Format an expression value correctly based on field type.
    
    Args:
        value: The value to format
        field_type: Esri field type
        
    Returns:
        Properly formatted expression string
    """
    if field_type in NUMERIC_FIELD_TYPES:
        # Numbers should not be quoted
        try:
            # Validate it's a valid number
            float(value)
            return value
        except ValueError:
            logger.warning(f"Value '{value}' is not a valid number for field type {field_type}, wrapping in quotes")
            return f'"{value}"'
    
    elif field_type in DATE_FIELD_TYPES:
        # Dates should use Date() function or timestamp
        if value.startswith("Date(") or value.isdigit():
            return value
        # Try to parse as ISO date and convert to timestamp
        try:
            from datetime import datetime
            dt = datetime.strptime(value, "%Y-%m-%d")
            timestamp = int(dt.timestamp() * 1000)
            return str(timestamp)
        except ValueError:
            logger.warning(f"Value '{value}' could not be parsed as date, wrapping in quotes")
            return f'"{value}"'
    
    else:
        # Strings should be quoted
        return f'"{value}"'


def validate_expression_references(
    webmap_data: Dict,
    form_elements: List[Dict],
    layer_title: str = "Unknown"
) -> Tuple[bool, List[str]]:
    """
    Validate that all expression references in form elements exist in expressionInfos.
    
    Args:
        webmap_data: The web map data dictionary
        form_elements: List of form elements to validate
        layer_title: Layer title for error messages
        
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    
    # Get all defined expression names
    defined_expressions = set()
    if "expressionInfos" in webmap_data:
        for expr in webmap_data["expressionInfos"]:
            if "name" in expr:
                defined_expressions.add(expr["name"])
    
    # Expression properties to check
    expression_props = ["valueExpression", "editableExpression", "visibilityExpression", "requiredExpression"]
    
    def check_element(element: Dict, path: str = "") -> None:
        """Recursively check elements for expression references."""
        for prop in expression_props:
            if prop in element:
                expr_name = element[prop]
                if expr_name and expr_name not in defined_expressions:
                    errors.append(
                        f"Layer '{layer_title}'{path}: {prop} references undefined expression '{expr_name}'"
                    )
        
        # Check nested elements (groups)
        if element.get("type") == "group" and "elements" in element:
            group_path = f"{path} > {element.get('label', 'Group')}"
            for nested in element["elements"]:
                check_element(nested, group_path)
    
    for element in form_elements:
        check_element(element)
    
    return (len(errors) == 0, errors)


def validate_expression_types(
    webmap_data: Dict,
    form_elements: List[Dict],
    field_types: Dict[str, str],
    layer_title: str = "Unknown"
) -> Tuple[bool, List[str]]:
    """
    Validate that expression return types match field types.
    
    Args:
        webmap_data: The web map data dictionary
        form_elements: List of form elements to validate
        field_types: Dict mapping field names to their Esri field types
        layer_title: Layer title for error messages
        
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    warnings = []
    
    # Build map of expression names to their return types
    expr_return_types = {}
    if "expressionInfos" in webmap_data:
        for expr in webmap_data["expressionInfos"]:
            if "name" in expr and "returnType" in expr:
                expr_return_types[expr["name"]] = expr["returnType"]
    
    def check_element(element: Dict, path: str = "") -> None:
        """Recursively check elements for type mismatches."""
        if element.get("type") == "field" and "fieldName" in element:
            field_name = element["fieldName"]
            field_type = field_types.get(field_name, "esriFieldTypeString")
            expected_return_type = get_expression_return_type(field_type)
            
            # Check valueExpression return type matches field type
            if "valueExpression" in element:
                expr_name = element["valueExpression"]
                actual_return_type = expr_return_types.get(expr_name, "unknown")
                
                if actual_return_type != "unknown" and actual_return_type != expected_return_type:
                    warnings.append(
                        f"Layer '{layer_title}'{path}: Field '{field_name}' is {field_type}, "
                        f"but valueExpression '{expr_name}' returns '{actual_return_type}' "
                        f"(expected '{expected_return_type}')"
                    )
            
            # Check that editableExpression is false when valueExpression is used
            if "valueExpression" in element:
                editable_expr = element.get("editableExpression", "")
                if editable_expr and editable_expr != "expr/system/false":
                    actual_return = expr_return_types.get(editable_expr)
                    # If editableExpression evaluates to true, that's a problem
                    if editable_expr == "expr/system/true":
                        errors.append(
                            f"Layer '{layer_title}'{path}: Field '{field_name}' has valueExpression "
                            f"but editableExpression is 'expr/system/true'. "
                            "Fields with calculated values should not be editable."
                        )
        
        # Check constraint expressions return boolean
        for prop in ["editableExpression", "visibilityExpression", "requiredExpression"]:
            if prop in element:
                expr_name = element[prop]
                actual_return_type = expr_return_types.get(expr_name, "unknown")
                if actual_return_type != "unknown" and actual_return_type != "boolean":
                    errors.append(
                        f"Layer '{layer_title}'{path}: {prop} '{expr_name}' returns '{actual_return_type}' "
                        "but must return 'boolean'"
                    )
        
        # Check nested elements (groups)
        if element.get("type") == "group" and "elements" in element:
            group_path = f"{path} > {element.get('label', 'Group')}"
            for nested in element["elements"]:
                check_element(nested, group_path)
    
    for element in form_elements:
        check_element(element)
    
    # Log warnings but don't fail validation
    for warning in warnings:
        logger.warning(warning)
    
    return (len(errors) == 0, errors)


def validate_no_nested_groups(
    form_elements: List[Dict],
    layer_title: str = "Unknown",
    depth: int = 0
) -> Tuple[bool, List[str]]:
    """
    Validate that there are no nested groups (ArcGIS doesn't support nested groups).
    
    Args:
        form_elements: List of form elements to validate
        layer_title: Layer title for error messages
        depth: Current nesting depth
        
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    
    for element in form_elements:
        if element.get("type") == "group":
            if depth > 0:
                errors.append(
                    f"Layer '{layer_title}': Nested groups are not supported. "
                    f"Group '{element.get('label', 'Unknown')}' is inside another group."
                )
            
            # Check for nested groups within this group
            if "elements" in element:
                for nested in element["elements"]:
                    if nested.get("type") == "group":
                        errors.append(
                            f"Layer '{layer_title}': Nested groups are not supported. "
                            f"Group '{nested.get('label', 'Unknown')}' is inside group '{element.get('label', 'Unknown')}'."
                        )
    
    return (len(errors) == 0, errors)


def validate_field_existence(
    form_elements: List[Dict],
    layer_fields: List[str],
    layer_title: str = "Unknown"
) -> Tuple[bool, List[str]]:
    """
    Validate that all field references in form elements exist in the layer schema.
    
    Args:
        form_elements: List of form elements to validate
        layer_fields: List of field names in the layer
        layer_title: Layer title for error messages
        
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    
    def check_element(element: Dict, path: str = "") -> None:
        """Recursively check elements for field references."""
        if element.get("type") == "field" and "fieldName" in element:
            field_name = element["fieldName"]
            if field_name not in layer_fields:
                errors.append(
                    f"Layer '{layer_title}'{path}: Field '{field_name}' does not exist in the layer schema"
                )
        
        # Check nested elements (groups)
        if element.get("type") == "group" and "elements" in element:
            group_path = f"{path} > {element.get('label', 'Group')}"
            for nested in element["elements"]:
                check_element(nested, group_path)
    
    for element in form_elements:
        check_element(element)
    
    return (len(errors) == 0, errors)


def validate_form_structure(
    webmap_data: Dict,
    layer: Dict,
    feature_layer: Optional[FeatureLayer] = None,
    layer_title: str = "Unknown"
) -> Tuple[bool, List[str]]:
    """
    Comprehensive validation of form structure before saving.
    
    Validates:
    - All referenced expressions exist in expressionInfos
    - Expression return types match field types
    - No nested groups in formElements
    - editableExpression is false when valueExpression is used
    - All field names exist in layer schema
    - formInfo and formElements structure is valid
    
    Args:
        webmap_data: The web map data dictionary
        layer: The layer dictionary containing formInfo
        feature_layer: Optional FeatureLayer for field validation
        layer_title: Layer title for error messages
        
    Returns:
        Tuple of (is_valid, list of error messages)
    """
    all_errors = []
    
    # Check formInfo exists
    if "formInfo" not in layer:
        all_errors.append(f"Layer '{layer_title}': No formInfo found")
        return (False, all_errors)
    
    form_info = layer["formInfo"]
    
    # Check formElements exists
    if "formElements" not in form_info:
        all_errors.append(f"Layer '{layer_title}': No formElements found in formInfo")
        return (False, all_errors)
    
    form_elements = form_info["formElements"]
    
    # Validate expression references
    valid, errors = validate_expression_references(webmap_data, form_elements, layer_title)
    all_errors.extend(errors)
    
    # Validate no nested groups
    valid, errors = validate_no_nested_groups(form_elements, layer_title)
    all_errors.extend(errors)
    
    # Validate field existence and expression types if we have feature layer info
    if feature_layer:
        try:
            fields = feature_layer.properties.fields
            layer_fields = [f.get("name") for f in fields]
            field_types = {f.get("name"): f.get("type", "esriFieldTypeString") for f in fields}
            
            # Validate field existence
            valid, errors = validate_field_existence(form_elements, layer_fields, layer_title)
            all_errors.extend(errors)
            
            # Validate expression types
            valid, errors = validate_expression_types(webmap_data, form_elements, field_types, layer_title)
            all_errors.extend(errors)
            
        except Exception as e:
            logger.warning(f"Could not validate fields for layer '{layer_title}': {e}")
    
    is_valid = len(all_errors) == 0
    
    if is_valid:
        logger.info(f"Layer '{layer_title}': Form structure validation passed")
    else:
        logger.warning(f"Layer '{layer_title}': Form structure validation failed with {len(all_errors)} error(s)")
        for error in all_errors:
            logger.warning(f"  - {error}")
    
    return (is_valid, all_errors)


def find_field_element(form_elements: List[Dict], field_name: str) -> Optional[Dict]:
    """
    Recursively search for a field element in form elements, including within groups.
    
    Args:
        form_elements: The list of form elements to search
        field_name: The name of the field to find
        
    Returns:
        Optional[Dict]: The element if found, otherwise None
    """
    for element in form_elements:
        # Check if this is the target field element
        if element.get("fieldName") == field_name:
            return element
        
        # If this is a group element, search within its elements
        if element.get("type") == "group" and "elements" in element:
            nested_element = find_field_element(element["elements"], field_name)
            if nested_element:
                return nested_element
    
    return None

def find_or_create_group(form_elements: List[Dict], group_name: str) -> Dict:
    """
    Find a group element by name or create it if it doesn't exist.
    
    Args:
        form_elements: The list of form elements to search
        group_name: The name of the group to find or create
        
    Returns:
        Dict: The group element
    """
    # Look for an existing group with the specified name
    for element in form_elements:
        if element.get("type") == "group" and element.get("label") == group_name:
            logger.info(f"Found existing '{group_name}' group")
            # Ensure the elements array exists
            if "elements" not in element:
                element["elements"] = []
            return element
    
    # Create a new group if not found
    new_group = {
        "type": "group",
        "label": group_name,
        "elements": []
    }
    form_elements.append(new_group)
    logger.info(f"Created new '{group_name}' group")
    return new_group

def update_field_element(element: Dict, expression_name: str, field_name: str = None, 
                         label: str = None, editable: bool = False) -> bool:
    """
    Update an existing field element with new values.
    
    Args:
        element: The element to update
        expression_name: The name of the expression to use
        field_name: The name of the field (if changing)
        label: The label for the field (if changing)
        editable: Whether the field should be editable
        
    Returns:
        bool: True if the element was updated, False if no changes were needed
    """
    changes_made = False
    
    # Check if the element already has the correct valueExpression
    if element.get("valueExpression") != expression_name:
        element["valueExpression"] = expression_name
        changes_made = True
    
    # Set editableExpression based on editable flag
    editable_expr = "expr/system/true" if editable else "expr/system/false"
    if element.get("editableExpression") != editable_expr:
        element["editableExpression"] = editable_expr
        changes_made = True
    
    # Update field name if provided and different
    if field_name and element.get("fieldName") != field_name:
        element["fieldName"] = field_name
        changes_made = True
    
    # Update label if provided and different
    if label and element.get("label") != label:
        element["label"] = label
        changes_made = True
    
    if changes_made:
        logger.info(f"Updated field element for '{field_name or element.get('fieldName')}' with expression '{expression_name}'")
    else:
        logger.info(f"Field element already has the correct properties")
    
    return changes_made

def add_field_form_element(form_elements: List[Dict], field_name: str, expression_name: str, 
                           group_name: str = "Metadata", label: str = None, 
                           editable: bool = False, move_if_exists: bool = True) -> bool:
    """
    Add a field element to a group if it doesn't exist, or update an existing element.
    
    Args:
        form_elements: The list of form elements
        field_name: The name of the field
        expression_name: The name of the expression to use
        group_name: The name of the group to add the element to
        label: The label for the field (defaults to formatted field name)
        editable: Whether the field should be editable
        move_if_exists: Whether to move the element to the specified group if it exists elsewhere
        
    Returns:
        bool: True if an element was added or updated, False otherwise
    """
    # Generate a label if not provided
    if label is None:
        label = ' '.join(word.capitalize() for word in field_name.replace('_', ' ').split())
    
    # Check if the field element already exists anywhere in the form
    existing_element = find_field_element(form_elements, field_name)
    
    if existing_element:
        logger.info(f"Field element for '{field_name}' already exists")
        
        # Check if the element is in a group
        in_group = False
        parent_group = None
        
        # Find the parent group of the existing element
        for element in form_elements:
            if element.get("type") == "group" and "elements" in element:
                if existing_element in element["elements"]:
                    in_group = True
                    parent_group = element
                    break
        
        # If move_if_exists is True and the element is not in the correct group, move it
        if move_if_exists and (not in_group or parent_group.get("label") != group_name):
            if parent_group:
                # Remove from current group
                parent_group["elements"].remove(existing_element)
                logger.info(f"Removed field element from '{parent_group.get('label')}' group")
            elif existing_element in form_elements:
                # Remove from top level
                form_elements.remove(existing_element)
                logger.info("Removed field element from top level")
            
            # Add to the correct group
            target_group = find_or_create_group(form_elements, group_name)
            target_group["elements"].append(existing_element)
            logger.info(f"Moved field element to '{group_name}' group")
        
        # Update the element properties
        return update_field_element(existing_element, expression_name, field_name, label, editable)
    
    # Find or create the target group
    target_group = find_or_create_group(form_elements, group_name)
    
    # Add the field element to the target group
    target_group["elements"].append({
        "label": label,
        "type": "field",
        "editableExpression": "expr/system/true" if editable else "expr/system/false",
        "fieldName": field_name,
        "inputType": {
            "type": "text-box",
            "maxLength": 255,
            "minLength": 0
        },
        "valueExpression": expression_name
    })
    logger.info(f"Added field element '{field_name}' to '{group_name}' group")
    
    return True

def find_layer_by_name(layers: List[Dict], layer_name: str) -> Optional[Tuple[Dict, List[str]]]:
    """
    Find a layer by name in the web map, including in nested group layers.
    
    Args:
        layers: The list of layers to search
        layer_name: The name of the layer to find
        
    Returns:
        Optional[Tuple[Dict, List[str]]]: A tuple containing the layer and its path if found, otherwise None
    """
    # Process all layers including nested ones using the shared utility
    # We wrap the layers list in a dictionary to match the expected structure
    for layer, path_prefix in process_webmap_layers({OPERATIONAL_LAYERS_KEY: layers}, include_path=True):
        layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
        
        # Check if this is the target layer
        if layer_title == layer_name:
            logger.info(f"Found layer '{layer_name}' at path: {'/'.join(path_prefix) if path_prefix else 'root'}")
            return (layer, path_prefix)
    
    logger.warning(f"Layer '{layer_name}' not found in the web map")
    return None

def extract_form_elements(layer: Dict) -> Dict[str, Dict]:
    """
    Extract form element configurations from a layer.
    
    Args:
        layer: The layer dictionary
        
    Returns:
        Dict[str, Dict]: A dictionary mapping field names to their form element configurations
    """
    form_elements = {}
    
    # Check if the layer has formInfo
    if "formInfo" not in layer:
        logger.info(f"Layer '{layer.get('title', 'Unnamed Layer')}' does not have formInfo")
        return form_elements
    
    # Check if formInfo has formElements
    if "formElements" not in layer["formInfo"]:
        logger.info(f"Layer '{layer.get('title', 'Unnamed Layer')}' does not have formElements")
        return form_elements
    
    # Process all form elements including those in groups
    elements_to_process = layer["formInfo"]["formElements"].copy()
    
    while elements_to_process:
        element = elements_to_process.pop(0)
        
        # If this is a field element, add it to the result
        if element.get("type") == "field" and "fieldName" in element:
            field_name = element["fieldName"]
            form_elements[field_name] = element.copy()
            logger.debug(f"Extracted form element for field '{field_name}'")
        
        # If this is a group element, add its elements to the processing queue
        if element.get("type") == "group" and "elements" in element:
            elements_to_process.extend(element["elements"])
    
    logger.info(f"Extracted {len(form_elements)} form elements from layer '{layer.get('title', 'Unnamed Layer')}'")
    return form_elements


def _extract_expression_references(form_elements: List[Dict]) -> set:
    """
    Extract all expression names referenced by form elements.
    
    Args:
        form_elements: List of form elements to scan
        
    Returns:
        Set of expression names referenced by the form elements
    """
    expression_names = set()
    expression_props = ["valueExpression", "editableExpression", "visibilityExpression", "requiredExpression"]
    
    elements_to_process = list(form_elements)
    while elements_to_process:
        element = elements_to_process.pop(0)
        
        # Check expression properties
        for prop in expression_props:
            if prop in element and element[prop]:
                expression_names.add(element[prop])
        
        # Process nested elements (groups)
        if element.get("type") == "group" and "elements" in element:
            elements_to_process.extend(element["elements"])
    
    return expression_names


def copy_layer_form_to_webmap(
    layer: Dict,
    feature_layer: FeatureLayer,
    gis: GIS,
    webmap_data: Optional[Dict] = None
) -> bool:
    """
    Copy formInfo from a layer item to the webmap layer configuration.
    
    When a layer has a form defined on the layer item but not in the webmap,
    this function copies the layer's form to the webmap so it can be modified.
    
    Args:
        layer: The layer dictionary from the webmap's operationalLayers
        feature_layer: The FeatureLayer object
        gis: The authenticated GIS object
        webmap_data: Optional webmap data dict for copying expressionInfos
        
    Returns:
        True if form was copied, False otherwise
    """
    layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
    
    # Check if layer already has formInfo in webmap
    if "formInfo" in layer and "formElements" in layer.get("formInfo", {}):
        logger.debug(f"Layer '{layer_title}' already has formInfo in webmap, skipping copy")
        return False
    
    # Get formInfo from layer item
    layer_form_info = get_layer_item_form_info(feature_layer, gis)
    
    if not layer_form_info:
        logger.debug(f"No formInfo found on layer item for '{layer_title}'")
        return False
    
    if "formElements" not in layer_form_info:
        logger.debug(f"Layer item formInfo for '{layer_title}' has no formElements")
        return False
    
    # Copy the formInfo to the webmap layer
    layer["formInfo"] = layer_form_info.copy()
    logger.info(f"Copied formInfo from layer item to webmap for layer '{layer_title}'")
    
    # If webmap_data is provided, copy expressionInfos to webmap's top level
    if webmap_data:
        ensure_expression_infos(webmap_data)
        
        # Get existing expression names in webmap
        existing_expr_names = {
            expr.get("name") for expr in webmap_data.get("expressionInfos", [])
        }
        
        # Build a map of available expressions from the layer form
        available_expressions = {}
        for expr_info in layer_form_info.get("expressionInfos", []):
            expr_name = expr_info.get("name")
            if expr_name:
                available_expressions[expr_name] = expr_info
        
        # Extract all expression references from form elements
        referenced_expressions = _extract_expression_references(layer_form_info.get("formElements", []))
        
        # Copy all referenced expressions that exist in layer form and not in webmap
        copied_count = 0
        missing_expressions = []
        for expr_name in referenced_expressions:
            if expr_name in existing_expr_names:
                continue  # Already in webmap
            
            if expr_name in available_expressions:
                webmap_data["expressionInfos"].append(available_expressions[expr_name].copy())
                logger.debug(f"Copied expression '{expr_name}' from layer form to webmap")
                copied_count += 1
            else:
                # Expression referenced but not found in layer form - log warning
                missing_expressions.append(expr_name)
        
        if copied_count > 0:
            logger.info(f"Copied {copied_count} expressions from layer '{layer_title}' to webmap")
        
        if missing_expressions:
            logger.warning(f"Layer '{layer_title}' references expressions not found in layer item: {missing_expressions}")
    
    return True


def copy_expressions_from_form_elements(webmap_data: Dict, form_elements: Dict[str, Dict]) -> None:
    """
    Copy expressions used by form elements to the web map's expressionInfos.
    
    Args:
        webmap_data: The web map data dictionary
        form_elements: A dictionary mapping field names to their form element configurations
    """
    # Ensure expressionInfos exists in the web map data
    ensure_expression_infos(webmap_data)
    
    # Get all expression names used by form elements
    expression_names = set()
    for field_name, element in form_elements.items():
        if "valueExpression" in element:
            expression_names.add(element["valueExpression"])
        if "editableExpression" in element:
            expression_names.add(element["editableExpression"])
        if "visibleExpression" in element:
            expression_names.add(element["visibleExpression"])
    
    # Add system expressions if needed
    if "expr/system/false" in expression_names and not has_expression_info(webmap_data, "expr/system/false"):
        webmap_data["expressionInfos"].append({
            "expression": "false",
            "name": "expr/system/false",
            "returnType": "boolean",
            "title": "False"
        })
        logger.info("Added system/false expression")
    
    if "expr/system/true" in expression_names and not has_expression_info(webmap_data, "expr/system/true"):
        webmap_data["expressionInfos"].append({
            "expression": "true",
            "name": "expr/system/true",
            "returnType": "boolean",
            "title": "True"
        })
        logger.info("Added system/true expression")
    
    # Copy custom expressions from the source web map
    for expression_name in expression_names:
        # Skip system expressions
        if expression_name in ["expr/system/false", "expr/system/true"]:
            continue
        
        # Skip if the expression already exists
        if has_expression_info(webmap_data, expression_name):
            continue
        
        # Find the expression in the web map
        if "expressionInfos" in webmap_data:
            for expr in webmap_data["expressionInfos"]:
                if expr.get("name") == expression_name:
                    # Add the expression to the web map
                    webmap_data["expressionInfos"].append(expr.copy())
                    logger.info(f"Copied expression '{expression_name}' to the web map")
                    break
            else:
                # Expression not found, add a placeholder
                add_custom_expression(webmap_data, expression_name)
                logger.warning(f"Expression '{expression_name}' not found, added placeholder")

def _copy_missing_expressions_from_layer_item(
    layer: Dict,
    feature_layer: FeatureLayer,
    gis: GIS,
    webmap_data: Dict
) -> int:
    """
    Copy missing expressions from layer item to webmap for an existing form.
    
    When a webmap form references expressions that don't exist in the webmap's
    expressionInfos, this function tries to find and copy them from the layer item.
    
    Args:
        layer: The layer dictionary with formInfo
        feature_layer: The FeatureLayer object
        gis: The authenticated GIS object
        webmap_data: The webmap data dict
        
    Returns:
        Number of expressions copied
    """
    layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
    
    if "formInfo" not in layer or "formElements" not in layer.get("formInfo", {}):
        return 0
    
    # Get existing expressions in webmap
    ensure_expression_infos(webmap_data)
    existing_expr_names = {
        expr.get("name") for expr in webmap_data.get("expressionInfos", [])
    }
    
    # Extract all expression references from the form
    referenced_expressions = _extract_expression_references(layer["formInfo"]["formElements"])
    
    # Find missing expressions
    missing_expressions = referenced_expressions - existing_expr_names
    
    if not missing_expressions:
        return 0
    
    logger.debug(f"Layer '{layer_title}' has {len(missing_expressions)} missing expressions: {missing_expressions}")
    
    # Try to get expressions from layer item
    layer_form_info = get_layer_item_form_info(feature_layer, gis)
    
    if not layer_form_info:
        logger.warning(f"Could not fetch layer item to find missing expressions for '{layer_title}'")
        return 0
    
    # Build map of available expressions from layer item
    available_expressions = {}
    for expr_info in layer_form_info.get("expressionInfos", []):
        expr_name = expr_info.get("name")
        if expr_name:
            available_expressions[expr_name] = expr_info
    
    # Copy missing expressions that exist in layer item
    copied_count = 0
    for expr_name in missing_expressions:
        if expr_name in available_expressions:
            webmap_data["expressionInfos"].append(available_expressions[expr_name].copy())
            logger.info(f"Copied missing expression '{expr_name}' from layer item to webmap")
            copied_count += 1
        else:
            logger.debug(f"Expression '{expr_name}' not found in layer item for '{layer_title}'")
    
    return copied_count


def update_layer_form_info(layer: Dict, feature_layer: FeatureLayer, field_name: str, 
                           expression_name: str, group_name: str = "Metadata", 
                           label: str = None, editable: bool = False,
                           gis: Optional[GIS] = None, webmap_data: Optional[Dict] = None) -> bool:
    """
    Update the formInfo for a layer to include the specified field.
    
    If the webmap doesn't have formInfo for this layer but the layer item does,
    the form will be copied from the layer item first.
    
    Also checks for and copies any missing expressions from the layer item.
    
    Args:
        layer: The layer dictionary
        feature_layer: The feature layer object
        field_name: The name of the field to add
        expression_name: The name of the expression to use
        group_name: The name of the group to add the element to
        label: The label for the field (defaults to formatted field name)
        editable: Whether the field should be editable
        gis: Optional GIS object for loading layer item forms
        webmap_data: Optional webmap data dict for copying expressionInfos
        
    Returns:
        bool: True if the layer was updated, False otherwise
    """
    layer_title = layer.get("title", "Unnamed Layer")
    
    # Check if the layer has formInfo - if not, try to load from layer item
    if "formInfo" not in layer:
        if gis is not None:
            # Try to copy form from layer item
            copied = copy_layer_form_to_webmap(layer, feature_layer, gis, webmap_data)
            if copied:
                logger.info(f"Loaded form from layer item for '{layer_title}'")
            else:
                logger.info(f"Layer '{layer_title}' does not have formInfo in webmap or layer item, skipping")
                return False
        else:
            logger.info(f"Layer '{layer_title}' does not have formInfo, skipping")
            return False
    elif gis is not None and webmap_data is not None:
        # Form exists in webmap - check for missing expressions and try to copy from layer item
        _copy_missing_expressions_from_layer_item(layer, feature_layer, gis, webmap_data)
    
    # Check if the layer has the target field
    if not layer_contains_field(feature_layer, field_name):
        logger.info(f"Layer '{layer_title}' does not have '{field_name}' field, skipping")
        return False
    
    # Check if formInfo has formElements
    if "formElements" not in layer["formInfo"]:
        layer["formInfo"]["formElements"] = []
    
    # Add the field form element
    result = add_field_form_element(
        layer["formInfo"]["formElements"], 
        field_name, 
        expression_name, 
        group_name, 
        label, 
        editable
    )
    
    if result:
        logger.info(f"Updated form element '{field_name}' in layer '{layer_title}'")
    
    return result

def update_webmap_forms(
    webmap_item_id: str,
    gis: GIS,
    field_name: str = "project_number",
    expression_name: str = "expr/set-project-number",
    expression_value: Optional[str] = None,
    group_name: str = DEFAULT_GROUP_NAME,
    field_label: Optional[str] = None,
    editable: bool = False
) -> List[str]:
    """
    Update the formInfo and expressionInfos in the web map for a specified field.
    
    Args:
        webmap_item_id: The ID of the web map to update
        gis: The authenticated GIS object
        field_name: The name of the field to add/update
        expression_name: The name of the expression to use
        expression_value: The value for the expression (random if not provided)
        group_name: The name of the group to add the element to
        field_label: The label for the field (defaults to formatted field name)
        editable: Whether the field should be editable
        
    Returns:
        List[str]: A list of updated layer URLs
        
    Note: This function will add the necessary expressionInfos to the web map even if
    no layers are updated. This ensures that the expressions are available for future use.
    """
    logger.info(f"Starting form update process for web map {webmap_item_id}")
    logger.info(f"Target field: {field_name}")
    logger.info(f"Expression: {expression_name}")
    logger.info(f"Group: {group_name}")
    
    # Input validation
    if not webmap_item_id:
        logger.error("Missing required webmap_item_id parameter")
        return []
    
    # Retrieve the web map item
    try:
        webmap_item = get_webmap_item(webmap_item_id, gis)
    except (WebMapNotFoundError, InvalidWebMapError) as e:
        logger.error(str(e))
        return []
    
    try:
        # Get the web map data (JSON)
        webmap_data = webmap_item.get_data()
        
        if OPERATIONAL_LAYERS_KEY not in webmap_data:
            logger.warning("No operational layers found in the webmap data")
            return []
        
        # Add or update the custom expression in the web map
        add_custom_expression(webmap_data, expression_name, expression_value, update_if_exists=True)
        
        # Process all layers including nested ones
        updated_layers = []
        
        for layer, path_prefix in process_webmap_layers(webmap_data, include_path=True):
            layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
            
            # Log the current layer being processed with its full path
            current_path = "/".join(path_prefix + [layer_title]) if path_prefix else layer_title
            logger.info(f"Processing layer: {current_path}")
            
            # Process feature layers with URLs
            if URL_KEY in layer:
                layer_url = layer[URL_KEY]
                
                try:
                    # Create a FeatureLayer to examine its fields
                    feature_layer = FeatureLayer(layer_url, gis=gis)
                    
                    # Update the layer's formInfo
                    if update_layer_form_info(
                        layer, 
                        feature_layer, 
                        field_name, 
                        expression_name, 
                        group_name, 
                        field_label, 
                        editable,
                        gis=gis,
                        webmap_data=webmap_data
                    ):
                        updated_layers.append(layer_url)
                except Exception as e:
                    logger.error(f"Error processing layer '{layer_title}': {str(e)}")
            else:
                logger.debug(f"Layer '{layer_title}' does not have a URL, skipping")
        
        logger.info(f"Updated {len(updated_layers)} layers in total")
        
        # Validate form structure before saving
        validation_errors = []
        for layer, _ in process_webmap_layers(webmap_data):
            if URL_KEY not in layer:
                continue
            
            layer_url = layer[URL_KEY]
            layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
            
            # Only validate layers that were updated
            if layer_url not in updated_layers:
                continue
            
            # Try to get feature layer for full validation
            try:
                feature_layer = FeatureLayer(layer_url, gis=gis)
            except Exception:
                feature_layer = None
            
            # Validate form structure
            is_valid, errors = validate_form_structure(webmap_data, layer, feature_layer, layer_title)
            if not is_valid:
                validation_errors.extend(errors)
        
        # If validation failed, log errors and abort
        if validation_errors:
            logger.error(f"Form validation failed with {len(validation_errors)} error(s)")
            for error in validation_errors:
                logger.error(f"  - {error}")
            return []
        
        logger.info("Form structure validation passed")
        
        # Save the changes to the web map
        if DEBUG_MODE:
            logger.info("DEBUG MODE: Webmap update simulated. Changes not saved to the server.")
            return updated_layers
        else:
            try:
                logger.info("Saving changes to web map...")
                update_result = webmap_item.update(data=webmap_data)
                
                if update_result:
                    logger.info("Webmap item update operation completed successfully")
                    return updated_layers
                else:
                    logger.error("Failed to update webmap item")
                    return []
            except Exception as e:
                logger.error(f"Error updating webmap item: {e}")
                return []
    except Exception as e:
        logger.error(f"Error in update process: {e}")
        return []

def apply_form_elements_to_layer(
    layer: Dict, 
    feature_layer: FeatureLayer, 
    form_elements: Dict[str, Dict], 
    field_names: Optional[List[str]] = None
) -> List[str]:
    """
    Apply form element configurations to a layer.
    
    Args:
        layer: The layer dictionary
        feature_layer: The feature layer object
        form_elements: A dictionary mapping field names to their form element configurations
        field_names: Optional list of field names to apply (if None, all matching fields are applied)
        
    Returns:
        List[str]: A list of field names that were updated
    """
    layer_title = layer.get("title", "Unnamed Layer")
    updated_fields = []
    
    # Check if the layer has formInfo
    if "formInfo" not in layer:
        logger.info(f"Layer '{layer_title}' does not have formInfo, skipping")
        return updated_fields
    
    # Check if formInfo has formElements
    if "formElements" not in layer["formInfo"]:
        layer["formInfo"]["formElements"] = []
    
    # Get the list of fields to process
    fields_to_process = field_names if field_names else list(form_elements.keys())
    
    # Process each field
    for field_name in fields_to_process:
        # Skip if the field is not in the source form elements
        if field_name not in form_elements:
            logger.info(f"Field '{field_name}' not found in source form elements, skipping")
            continue
        
        # Skip if the layer doesn't have the field
        if not layer_contains_field(feature_layer, field_name):
            logger.info(f"Layer '{layer_title}' does not have '{field_name}' field, skipping")
            continue
        
        # Get the form element configuration
        element_config = form_elements[field_name]
        
        # Find the group name
        group_name = "Metadata"  # Default group name
        
        # Try to find the parent group of the element in the source layer
        for source_element in form_elements.values():
            if source_element.get("type") == "group" and "elements" in source_element:
                if any(e.get("fieldName") == field_name for e in source_element["elements"]):
                    group_name = source_element.get("label", "Metadata")
                    break
        
        # Add or update the field form element
        result = add_field_form_element(
            layer["formInfo"]["formElements"],
            field_name,
            element_config.get("valueExpression", ""),
            group_name,
            element_config.get("label", None),
            element_config.get("editableExpression") == "expr/system/true"
        )
        
        if result:
            logger.info(f"Updated form element '{field_name}' in layer '{layer_title}'")
            updated_fields.append(field_name)
    
    return updated_fields

def propagate_form_elements(
    webmap_item_id: str,
    source_layer_name: str,
    gis: GIS,
    target_layer_names: Optional[List[str]] = None,
    field_names: Optional[List[str]] = None
) -> Dict[str, List[str]]:
    """
    Propagate form element configurations from a source layer to target layers.
    
    Args:
        webmap_item_id: The ID of the web map
        source_layer_name: The name of the source layer to copy configurations from
        gis: The authenticated GIS object
        target_layer_names: Optional list of target layer names (if None, all layers are considered)
        field_names: Optional list of field names to propagate (if None, all matching fields are propagated)
        
    Returns:
        Dict[str, List[str]]: A dictionary mapping layer names to lists of updated field names
    """
    logger.info(f"Starting form element propagation for web map {webmap_item_id}")
    logger.info(f"Source layer: {source_layer_name}")
    if target_layer_names:
        logger.info(f"Target layers: {', '.join(target_layer_names)}")
    if field_names:
        logger.info(f"Fields to propagate: {', '.join(field_names)}")
    
    # Input validation
    if not webmap_item_id or not source_layer_name:
        logger.error("Missing required parameters")
        return {}
    
    # Retrieve the web map item
    try:
        webmap_item = get_webmap_item(webmap_item_id, gis)
    except (WebMapNotFoundError, InvalidWebMapError) as e:
        logger.error(str(e))
        return {}
    
    try:
        # Get the web map data (JSON)
        webmap_data = webmap_item.get_data()
        
        if OPERATIONAL_LAYERS_KEY not in webmap_data:
            logger.warning("No operational layers found in the webmap data")
            return {}
        
        # Find the source layer
        source_layer_result = find_layer_by_name(webmap_data[OPERATIONAL_LAYERS_KEY], source_layer_name)
        if not source_layer_result:
            logger.error(f"Source layer '{source_layer_name}' not found in the web map")
            return {}
        
        source_layer, source_path = source_layer_result
        
        # Check if the source layer has a URL
        if URL_KEY not in source_layer:
            logger.error(f"Source layer '{source_layer_name}' does not have a URL")
            return {}
        
        # Create a FeatureLayer for the source layer
        try:
            source_feature_layer = FeatureLayer(source_layer[URL_KEY], gis=gis)
        except Exception as e:
            logger.error(f"Error creating FeatureLayer for source layer: {str(e)}")
            return {}
        
        # Extract form element configurations from the source layer
        source_form_elements = extract_form_elements(source_layer)
        if not source_form_elements:
            logger.warning(f"No form elements found in source layer '{source_layer_name}'")
            return {}
        
        logger.info(f"Extracted {len(source_form_elements)} form elements from source layer '{source_layer_name}'")
        
        # Copy expressions used by form elements to the web map
        copy_expressions_from_form_elements(webmap_data, source_form_elements)
        
        # Process all layers including nested ones
        updated_layers = {}
        
        for layer, path_prefix in process_webmap_layers(webmap_data, include_path=True):
            layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
            
            # Skip the source layer
            if layer_title == source_layer_name:
                logger.info(f"Skipping source layer '{source_layer_name}'")
                continue
            
            # Skip if target_layer_names is provided and this layer is not in the list
            if target_layer_names and layer_title not in target_layer_names:
                # Still need to process child layers (which is handled by process_webmap_layers)
                # But here we just skip processing this specific layer
                logger.debug(f"Layer '{layer_title}' not in target layers list, skipping")
                continue
            
            # Log the current layer being processed with its full path
            current_path = "/".join(path_prefix + [layer_title]) if path_prefix else layer_title
            logger.info(f"Processing layer: {current_path}")
            
            # Process feature layers with URLs
            if URL_KEY in layer:
                layer_url = layer[URL_KEY]
                
                try:
                    # Create a FeatureLayer to examine its fields
                    feature_layer = FeatureLayer(layer_url, gis=gis)
                    
                    # Apply form element configurations to the layer
                    updated_fields = apply_form_elements_to_layer(
                        layer,
                        feature_layer,
                        source_form_elements,
                        field_names
                    )
                    
                    if updated_fields:
                        updated_layers[layer_title] = updated_fields
                except Exception as e:
                    logger.error(f"Error processing layer '{layer_title}': {str(e)}")
            else:
                logger.debug(f"Layer '{layer_title}' does not have a URL, skipping")
        
        logger.info(f"Updated {len(updated_layers)} layers in total")
        
        # Validate form structure before saving
        validation_errors = []
        for layer, _ in process_webmap_layers(webmap_data):
            layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
            
            # Only validate layers that were updated
            if layer_title not in updated_layers:
                continue
            
            if URL_KEY not in layer:
                continue
            
            # Try to get feature layer for full validation
            try:
                feature_layer = FeatureLayer(layer[URL_KEY], gis=gis)
            except Exception:
                feature_layer = None
            
            # Validate form structure
            is_valid, errors = validate_form_structure(webmap_data, layer, feature_layer, layer_title)
            if not is_valid:
                validation_errors.extend(errors)
        
        # If validation failed, log errors and abort
        if validation_errors:
            logger.error(f"Form validation failed with {len(validation_errors)} error(s)")
            for error in validation_errors:
                logger.error(f"  - {error}")
            return {}
        
        logger.info("Form structure validation passed")
        
        # Save the changes to the web map
        if DEBUG_MODE:
            logger.info("DEBUG MODE: Webmap update simulated. Changes not saved to the server.")
            return updated_layers
        else:
            try:
                logger.info("Saving changes to web map...")
                update_result = webmap_item.update(data=webmap_data)
                
                if update_result:
                    logger.info("Webmap item update operation completed successfully")
                    return updated_layers
                else:
                    logger.error("Failed to update webmap item")
                    return {}
            except Exception as e:
                logger.error(f"Error updating webmap item: {e}")
                return {}
    except Exception as e:
        logger.error(f"Error in propagation process: {e}")
        return {}

def update_webmap_forms_by_layer_config(
    webmap_item_id: str,
    layer_configs: Dict[str, Dict[str, Any]],
    gis: GIS,
    debug_mode: bool = False
) -> Dict[str, Any]:
    """
    Update form configurations for specific layers using per-layer configuration.
    
    Args:
        webmap_item_id: The ID of the web map to update
        layer_configs: Dictionary mapping layer URLs to their configuration:
            {
                "layer_url": {
                    "field_name": "field to configure in the form",
                    "expression_name": "expr/my-expression",
                    "expression_value": "optional value for expression",
                    "group_name": "Metadata",
                    "field_label": "Optional Label",
                    "editable": False
                }
            }
        gis: The authenticated GIS object
        debug_mode: Whether to simulate updates without saving
        
    Returns:
        Dictionary with results:
            {
                "updated_layers": List of layer URLs that were updated,
                "skipped_layers": List of layer URLs skipped (no formInfo or field),
                "errors": Dict mapping layer URLs to error messages,
                "expressions_added": List of expression names added
            }
    """
    logger.info(f"Starting per-layer form update process for web map {webmap_item_id}")
    logger.info(f"Processing {len(layer_configs)} layer configurations")
    
    result = {
        "updated_layers": [],
        "skipped_layers": [],
        "errors": {},
        "expressions_added": []
    }
    
    # Input validation
    if not webmap_item_id:
        logger.error("Missing webmap_item_id")
        return result
    
    if not layer_configs:
        logger.warning("No layer configurations provided")
        return result
    
    # Retrieve the web map item
    try:
        webmap_item = get_webmap_item(webmap_item_id, gis)
    except (WebMapNotFoundError, InvalidWebMapError) as e:
        logger.error(str(e))
        raise
    
    try:
        # Get the web map data (JSON)
        webmap_data = webmap_item.get_data()
        
        if OPERATIONAL_LAYERS_KEY not in webmap_data:
            logger.warning("No operational layers found in the webmap data")
            return result
        
        # First pass: collect field types and validate layers before adding expressions
        # This ensures expressions have the correct return type based on field type
        layer_field_types = {}  # layer_url -> field_type
        layers_to_process = []  # list of (layer, config, feature_layer) tuples
        
        for layer, _ in process_webmap_layers(webmap_data):
            if URL_KEY not in layer:
                continue
                
            layer_url = layer[URL_KEY]
            layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
            
            # Check if this layer is in our config
            if layer_url not in layer_configs:
                continue
            
            config = layer_configs[layer_url]
            field_name = config.get("field_name", "")
            expression_name = config.get("expression_name", "")
            group_name = config.get("group_name", DEFAULT_GROUP_NAME)
            field_label = config.get("field_label")
            editable = config.get("editable", False)
            
            if not field_name:
                logger.warning(f"Incomplete config for layer '{layer_title}': missing field_name")
                result["errors"][layer_url] = "Missing field_name in configuration"
                continue
            
            if not expression_name:
                logger.warning(f"Incomplete config for layer '{layer_title}': missing expression_name")
                result["errors"][layer_url] = "Missing expression_name in configuration"
                continue
            
            # Check if layer has formInfo
            if "formInfo" not in layer:
                logger.info(f"Layer '{layer_title}' does not have formInfo, skipping")
                result["skipped_layers"].append(layer_url)
                continue
            
            try:
                # Create a FeatureLayer to examine its fields
                feature_layer = FeatureLayer(layer_url, gis=gis)
                
                if not layer_contains_field(feature_layer, field_name):
                    logger.warning(f"Layer '{layer_title}' does not contain field '{field_name}'")
                    result["skipped_layers"].append(layer_url)
                    continue
                
                # Get field type for this field
                field_type = "esriFieldTypeString"  # Default
                try:
                    for field in feature_layer.properties.fields:
                        if field.get("name") == field_name:
                            field_type = field.get("type", "esriFieldTypeString")
                            break
                except Exception as e:
                    logger.warning(f"Could not get field type for '{field_name}': {e}")
                
                layer_field_types[layer_url] = field_type
                layers_to_process.append((layer, config, feature_layer, field_type))
                
            except Exception as e:
                logger.error(f"Error processing layer '{layer_title}': {str(e)}")
                result["errors"][layer_url] = str(e)
        
        # Collect all unique expressions needed with their field types
        expressions_to_add = {}  # expr_name -> (expr_value, field_type)
        for layer_url, config in layer_configs.items():
            expr_name = config.get("expression_name", "")
            if expr_name and layer_url in layer_field_types:
                expr_value = config.get("expression_value")
                field_type = layer_field_types.get(layer_url, "esriFieldTypeString")
                # Store expression with field type (first one wins if multiple layers use same expression)
                if expr_name not in expressions_to_add:
                    expressions_to_add[expr_name] = (expr_value, field_type)
        
        # Add or update all required expressions in the web map with correct field types
        for expr_name, (expr_value, field_type) in expressions_to_add.items():
            if add_custom_expression(webmap_data, expr_name, expr_value, field_type=field_type, update_if_exists=True):
                result["expressions_added"].append(expr_name)
        
        # Second pass: process layers (already validated in first pass)
        for layer, config, feature_layer, field_type in layers_to_process:
            layer_url = layer[URL_KEY]
            layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
            
            field_name = config.get("field_name", "")
            expression_name = config.get("expression_name", "")
            group_name = config.get("group_name", DEFAULT_GROUP_NAME)
            field_label = config.get("field_label")
            editable = config.get("editable", False)
            
            try:
                # Update the layer's formInfo
                if update_layer_form_info(
                    layer,
                    feature_layer,
                    field_name,
                    expression_name,
                    group_name,
                    field_label,
                    editable,
                    gis=gis,
                    webmap_data=webmap_data
                ):
                    logger.info(f"Updated form for layer '{layer_title}' on field '{field_name}'")
                    result["updated_layers"].append(layer_url)
                else:
                    result["skipped_layers"].append(layer_url)
                    
            except Exception as e:
                logger.error(f"Error processing layer '{layer_title}': {str(e)}")
                result["errors"][layer_url] = str(e)
        
        logger.info(f"Updated {len(result['updated_layers'])} layers, skipped {len(result['skipped_layers'])}, errors: {len(result['errors'])}")
        
        # Validate form structure before saving
        validation_errors = []
        for layer, _ in process_webmap_layers(webmap_data):
            if URL_KEY not in layer:
                continue
            
            layer_url = layer[URL_KEY]
            layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
            
            # Only validate layers that were updated
            if layer_url not in result["updated_layers"]:
                continue
            
            # Try to get feature layer for full validation
            try:
                feature_layer = FeatureLayer(layer_url, gis=gis)
            except Exception:
                feature_layer = None
            
            # Validate form structure
            is_valid, errors = validate_form_structure(webmap_data, layer, feature_layer, layer_title)
            if not is_valid:
                validation_errors.extend(errors)
        
        # If validation failed, add errors and abort
        if validation_errors:
            logger.error(f"Form validation failed with {len(validation_errors)} error(s)")
            for error in validation_errors:
                logger.error(f"  - {error}")
            result["errors"]["_validation"] = "; ".join(validation_errors)
            result["validation_errors"] = validation_errors
            return result
        
        logger.info("Form structure validation passed")
        
        # Save the changes to the web map
        if debug_mode or DEBUG_MODE:
            logger.info("DEBUG MODE: Webmap update simulated. Changes not saved to the server.")
            return result
        else:
            try:
                logger.info("Saving changes to web map...")
                update_result = webmap_item.update(data=webmap_data)
                
                if update_result:
                    logger.info("Webmap item update operation completed successfully")
                    return result
                else:
                    logger.error("Failed to update webmap item")
                    result["errors"]["_save"] = "Failed to save changes to web map"
                    return result
            except Exception as e:
                logger.error(f"Error updating webmap item: {e}")
                result["errors"]["_save"] = str(e)
                return result
    except Exception as e:
        logger.error(f"Error in update process: {e}")
        raise LayerProcessingError(f"Error in update process: {e}") from e


def update_webmap_forms_simplified(
    webmap_item_id: str,
    gis: GIS,
    layer_field_values: Dict[str, Dict[str, str]],
    debug_mode: bool = False
) -> Dict[str, Any]:
    """
    Simplified form update - auto-generates technical parameters from field name and value.
    
    This is a user-friendly wrapper around update_webmap_forms_by_layer_config that
    automatically generates expression names, labels, and other technical details
    from just the field name and default value.
    
    Args:
        webmap_item_id: The ID of the web map to update
        gis: The authenticated GIS object
        layer_field_values: Dict mapping layer URLs to simplified config:
            {
                "https://.../FeatureServer/0": {
                    "field_name": "project_number",
                    "default_value": "12345"
                }
            }
        debug_mode: Whether to simulate updates without saving
        
    Returns:
        Dictionary with results (same as update_webmap_forms_by_layer_config):
            {
                "updated_layers": List of layer URLs that were updated,
                "skipped_layers": List of layer URLs skipped,
                "errors": Dict mapping layer URLs to error messages,
                "expressions_added": List of expression names added
            }
    
    Auto-generation logic:
        - expression_name: "expr/set-{field_name}" (underscores become hyphens)
        - expression_value: The provided default_value
        - group_name: "Metadata" (constant)
        - field_label: field_name with underscores replaced by spaces, title-cased
        - editable: False (constant)
    """
    logger.info(f"Starting simplified form update for web map {webmap_item_id}")
    logger.info(f"Processing {len(layer_field_values)} layer configurations")
    
    # Convert simplified config to full layer_configs format
    layer_configs = {}
    for layer_url, config in layer_field_values.items():
        field_name = config.get("field_name", "")
        default_value = config.get("default_value", "")
        
        if not field_name:
            logger.warning(f"Skipping layer {layer_url}: missing field_name")
            continue
        
        if not default_value:
            logger.warning(f"Skipping layer {layer_url}: missing default_value")
            continue
        
        # Auto-generate technical parameters
        # Expression name: expr/set-project-number from project_number
        expression_name = f"expr/set-{field_name.replace('_', '-')}"
        
        # Label: "Project Number" from "project_number"
        field_label = field_name.replace("_", " ").title()
        
        layer_configs[layer_url] = {
            "field_name": field_name,
            "expression_name": expression_name,
            "expression_value": default_value,
            "group_name": DEFAULT_GROUP_NAME,
            "field_label": field_label,
            "editable": False
        }
        
        logger.debug(f"Generated config for {field_name}: expr={expression_name}, label={field_label}")
    
    if not layer_configs:
        logger.warning("No valid layer configurations after processing")
        return {
            "updated_layers": [],
            "skipped_layers": [],
            "errors": {},
            "expressions_added": []
        }
    
    # Delegate to the full configuration function
    return update_webmap_forms_by_layer_config(webmap_item_id, layer_configs, gis, debug_mode)


def test_propagate_form_elements(
    gis: GIS,
    webmap_item_id: str = "d1ea52f5280d4d57b5e331d21e00296e",
    source_layer_name: str = "Artifact Point",
    target_layer_names: Optional[List[str]] = None,
    field_names: Optional[List[str]] = None
) -> Dict[str, List[str]]:
    """
    Test function to demonstrate propagating form elements from a source layer to target layers.
    
    Args:
        gis: The authenticated GIS object
        webmap_item_id: The ID of the web map
        source_layer_name: The name of the source layer to copy configurations from
        target_layer_names: Optional list of target layer names (if None, all layers are considered)
        field_names: Optional list of field names to propagate (if None, all matching fields are propagated)
        
    Returns:
        Dict[str, List[str]]: A dictionary mapping layer names to lists of updated field names
    """
    logger.info("=== Starting Form Element Propagation Test ===")
    logger.info(f"Web Map ID: {webmap_item_id}")
    logger.info(f"Source Layer: {source_layer_name}")
    if target_layer_names:
        logger.info(f"Target Layers: {', '.join(target_layer_names)}")
    if field_names:
        logger.info(f"Fields: {', '.join(field_names)}")
    
    # Perform the propagation
    updated_layers = propagate_form_elements(
        webmap_item_id,
        source_layer_name,
        gis,
        target_layer_names,
        field_names
    )
    
    # Log results
    if updated_layers:
        logger.info(f"Successfully updated {len(updated_layers)} layers")
        for layer_name, fields in updated_layers.items():
            logger.info(f"  - {layer_name}: {', '.join(fields)}")
    else:
        logger.warning("No layers were updated")
    
    logger.info("=== Form Element Propagation Test Complete ===")
    return updated_layers

def test_webmap_forms_update(
    gis: GIS,
    webmap_item_id: str = "d1ea52f5280d4d57b5e331d21e00296e",
    field_name: str = "project_number",
    expression_name: str = "expr/set-project-number",
    expression_value: Optional[str] = None,
    group_name: str = DEFAULT_GROUP_NAME,
    field_label: Optional[str] = None,
    editable: bool = False
):
    """
    Test function to demonstrate updating a web map's forms.
    
    Args:
        gis: The authenticated GIS object
        webmap_item_id: The ID of the web map to update
        field_name: The name of the field to add/update
        expression_name: The name of the expression to use
        expression_value: The value for the expression (random if not provided)
        group_name: The name of the group to add the element to
        field_label: The label for the field (defaults to formatted field name)
        editable: Whether the field should be editable
    
    Returns:
        List[str]: A list of updated layer URLs
    """
    logger.info("=== Starting Web Map Forms Update Test ===")
    logger.info(f"Web Map ID: {webmap_item_id}")
    logger.info(f"Field: {field_name}")
    logger.info(f"Expression: {expression_name}")
    logger.info(f"Group: {group_name}")
    
    # Perform the update
    updated_layers = update_webmap_forms(
        webmap_item_id,
        gis,
        field_name,
        expression_name,
        expression_value,
        group_name,
        field_label,
        editable
    )
    
    # Log results
    if updated_layers:
        logger.info(f"Successfully updated {len(updated_layers)} layers")
    else:
        logger.warning("No layers were updated")
    
    logger.info("=== Web Map Forms Update Test Complete ===")
    return updated_layers

if __name__ == "__main__":
    import argparse
    from backend.utils.auth import authenticate_from_env
    
    # Create main argument parser
    parser = argparse.ArgumentParser(description="Utilities for updating form elements in ArcGIS web maps")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Create parser for the 'update' command
    update_parser = subparsers.add_parser("update", help="Update a specific field in all layers")
    update_parser.add_argument("webmap_id", help="ID of the web map to update")
    update_parser.add_argument("--field", default="project_number", help="Field name to add/update")
    update_parser.add_argument("--expression", default="expr/set-project-number", help="Expression name")
    update_parser.add_argument("--value", help="Expression value (random if not provided)")
    update_parser.add_argument("--group", default=DEFAULT_GROUP_NAME, help="Group name for the field")
    update_parser.add_argument("--label", help="Field label (derived from field name if not provided)")
    update_parser.add_argument("--editable", action="store_true", help="Make the field editable")
    
    # Create parser for the 'propagate' command
    propagate_parser = subparsers.add_parser("propagate", help="Propagate form elements from one layer to others")
    propagate_parser.add_argument("webmap_id", help="ID of the web map to update")
    propagate_parser.add_argument("--source", required=True, help="Name of the source layer to copy configurations from")
    propagate_parser.add_argument("--targets", help="Comma-separated list of target layer names (if omitted, all layers are considered)")
    propagate_parser.add_argument("--fields", help="Comma-separated list of field names to propagate (if omitted, all matching fields are propagated)")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Set debug mode
    globals()["DEBUG_MODE"] = args.debug
    
    # Set log level based on debug mode
    if DEBUG_MODE:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Get GIS connection - require environment variables
    try:
        gis = authenticate_from_env()
    except (ValueError, AuthenticationError) as e:
        logger.error(f"Authentication failed: {e}")
        logger.error("Please set ARCGIS_USERNAME and ARCGIS_PASSWORD environment variables")
        sys.exit(1)
    
    # Execute the appropriate command
    if args.command == "update":
        # Run the update function with provided arguments
        updated = test_webmap_forms_update(
            gis,
            args.webmap_id,
            args.field,
            args.expression,
            args.value,
            args.group,
            args.label,
            args.editable
        )
        
        print("---")
        if updated:
            print(f"Successfully updated {len(updated)} layers")
            
            # If in debug mode, add a note about simulated updates
            if DEBUG_MODE:
                print("Note: Running in DEBUG mode - changes were simulated and not saved to the server")
            else:
                print("Changes were verified and saved to the server")
        else:
            print("No layers were updated")
            print("Note: expressionInfos were still added to the web map")
            
            # If not in debug mode, provide more information about potential issues
            if not DEBUG_MODE:
                print("Possible issues:")
                print("  • The web map may not contain layers with formInfo")
                print(f"  • The layers may not have the '{args.field}' field")
                print("  • The server may not have accepted the changes")
                print("  • There might be permission issues with the web map")
                print("\nTry running with --debug to see more details")
    
    elif args.command == "propagate":
        # Parse target layers and field names
        target_layer_names = args.targets.split(",") if args.targets else None
        field_names = args.fields.split(",") if args.fields else None
        
        # Run the propagate function with provided arguments
        updated_layers = test_propagate_form_elements(
            gis,
            args.webmap_id,
            args.source,
            target_layer_names,
            field_names
        )
        
        print("---")
        if updated_layers:
            print(f"Successfully updated {len(updated_layers)} layers:")
            for layer_name, fields in updated_layers.items():
                print(f"  - {layer_name}: {', '.join(fields)}")
            
            # If in debug mode, add a note about simulated updates
            if DEBUG_MODE:
                print("\nNote: Running in DEBUG mode - changes were simulated and not saved to the server")
            else:
                print("\nChanges were verified and saved to the server")
        else:
            print("No layers were updated")
            
            # If not in debug mode, provide more information about potential issues
            if not DEBUG_MODE:
                print("Possible issues:")
                print(f"  • The source layer '{args.source}' may not exist in the web map")
                print("  • The source layer may not have any form elements")
                print("  • The target layers may not have matching fields")
                print("  • The server may not have accepted the changes")
                print("  • There might be permission issues with the web map")
                print("\nTry running with --debug to see more details")
    
    else:
        # No command specified, show help
        parser.print_help()
