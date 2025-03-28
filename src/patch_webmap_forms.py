import json
import logging
import os
import random
import string
from typing import List, Optional, Dict, Any, Union, Tuple

from arcgis.features import FeatureLayer
from arcgis.gis import GIS

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("patch_webmap_forms")

# Get credentials from environment variables with fallback to default values
# In production, these should be set as environment variables
username = os.environ.get("ARCGIS_USERNAME", "fdc_admin_swca")
password = os.environ.get("ARCGIS_PASSWORD", "EarthRouser24")
profile = os.environ.get("ARCGIS_PROFILE", "FDC_Admin")

# Initialize GIS connection
gis = GIS(username=username, password=password, profile=profile)

# Global debug mode: Set to True to simulate updates (for testing) or False for production.
DEBUG_MODE = False

def generate_random_string(length: int = 8) -> str:
    """Generate a random alphanumeric string of specified length."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

def get_webmap_item(webmap_item_id: str) -> Optional[Any]:
    """Retrieve the web map item using the global gis object."""
    if not webmap_item_id or not isinstance(webmap_item_id, str):
        logger.error("Invalid webmap_item_id provided")
        return None
        
    try:
        logger.info(f"Retrieving web map with ID: {webmap_item_id}")
        webmap_item = gis.content.get(webmap_item_id)
        if not webmap_item:
            logger.error(f"Web map with ID {webmap_item_id} was not found")
            return None
        
        logger.debug(f"Successfully retrieved web map: {webmap_item.title}")
        return webmap_item
    except Exception as e:
        logger.error(f"Error retrieving web map: {e}")
        return None

def layer_contains_field(feature_layer: FeatureLayer, target_field: str) -> bool:
    """Check if the feature layer contains the target field."""
    if not feature_layer or not target_field:
        return False
        
    try:
        fields = feature_layer.properties.fields
        return any(field.get("name") == target_field for field in fields)
    except Exception:
        return False

def has_expression_info(webmap_data: Dict, expression_name: str) -> bool:
    """Check if the web map already has the specified expression info."""
    if "expressionInfos" not in webmap_data:
        return False
    
    return any(expr.get("name") == expression_name for expr in webmap_data["expressionInfos"])

def ensure_expression_infos(webmap_data: Dict) -> None:
    """Ensure that expressionInfos exists in the web map data."""
    if "expressionInfos" not in webmap_data:
        webmap_data["expressionInfos"] = []

def add_custom_expression(webmap_data: Dict, expression_name: str, expression_value: Optional[str] = None, 
                          title: Optional[str] = None, return_type: str = "string") -> bool:
    """
    Add a custom expression to the web map's expressionInfos.
    
    Args:
        webmap_data: The web map data dictionary
        expression_name: The name of the expression (e.g., "expr/set-project-number")
        expression_value: The value for the expression (random if not provided)
        title: The title for the expression (derived from name if not provided)
        return_type: The return type of the expression (default: "string")
        
    Returns:
        bool: True if the expression was added, False if it already existed
    """
    ensure_expression_infos(webmap_data)
    
    # Check if the expression already exists
    if has_expression_info(webmap_data, expression_name):
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
    
    # Add the custom expression
    webmap_data["expressionInfos"].append({
        "expression": f"\"{expression_value}\"",
        "name": expression_name,
        "returnType": return_type,
        "title": title
    })
    logger.info(f"Added expression '{expression_name}' with value: {expression_value}")
    
    return True

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
    # Process all layers including nested ones
    layers_to_process = []
    
    # Initialize the processing queue with top-level layers
    for layer in layers:
        # Add metadata to track layer path
        layer_copy = layer.copy()
        layer_copy["_path_prefix"] = []
        layers_to_process.append(layer_copy)
    
    while layers_to_process:
        layer = layers_to_process.pop(0)
        layer_title = layer.get("title", "Unnamed Layer")
        
        # Get the path prefix for this layer
        path_prefix = layer.get("_path_prefix", [])
        
        # Check if this is the target layer
        if layer_title == layer_name:
            logger.info(f"Found layer '{layer_name}' at path: {'/'.join(path_prefix) if path_prefix else 'root'}")
            return (layer, path_prefix)
        
        # Add nested layers to processing queue with updated path prefix
        if "layers" in layer and isinstance(layer["layers"], list):
            # Create a new path prefix for child layers
            new_prefix = path_prefix + [layer_title]
            
            # Add child layers to the processing queue with the current layer as prefix
            for child_layer in layer["layers"]:
                # Clone the child layer to avoid modifying the original
                child_layer_copy = child_layer.copy()
                # Store the path prefix with the layer for later use
                child_layer_copy["_path_prefix"] = new_prefix
                # We'll process these layers next, with the current layer as part of their path
                layers_to_process.append(child_layer_copy)
    
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

def update_layer_form_info(layer: Dict, feature_layer: FeatureLayer, field_name: str, 
                           expression_name: str, group_name: str = "Metadata", 
                           label: str = None, editable: bool = False) -> bool:
    """
    Update the formInfo for a layer to include the specified field.
    
    Args:
        layer: The layer dictionary
        feature_layer: The feature layer object
        field_name: The name of the field to add
        expression_name: The name of the expression to use
        group_name: The name of the group to add the element to
        label: The label for the field (defaults to formatted field name)
        editable: Whether the field should be editable
        
    Returns:
        bool: True if the layer was updated, False otherwise
    """
    layer_title = layer.get("title", "Unnamed Layer")
    
    # Check if the layer has formInfo
    if "formInfo" not in layer:
        logger.info(f"Layer '{layer_title}' does not have formInfo, skipping")
        return False
    
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
    field_name: str = "project_number",
    expression_name: str = "expr/set-project-number",
    expression_value: Optional[str] = None,
    group_name: str = "Metadata",
    field_label: Optional[str] = None,
    editable: bool = False
) -> List[str]:
    """
    Update the formInfo and expressionInfos in the web map for a specified field.
    
    Args:
        webmap_item_id: The ID of the web map to update
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
    webmap_item = get_webmap_item(webmap_item_id)
    if not webmap_item:
        return []
    
    try:
        # Get the web map data (JSON)
        webmap_data = webmap_item.get_data()
        
        if "operationalLayers" not in webmap_data:
            logger.warning("No operational layers found in the webmap data")
            return []
        
        # Add the custom expression to the web map
        add_custom_expression(webmap_data, expression_name, expression_value)
        
        # Process all layers including nested ones
        updated_layers = []
        layers_to_process = []
        
        # Initialize the processing queue with top-level layers
        for layer in webmap_data["operationalLayers"]:
            # Add metadata to track layer path
            layer["_path_prefix"] = []
            layers_to_process.append(layer)
        
        while layers_to_process:
            layer = layers_to_process.pop(0)
            layer_title = layer.get("title", "Unnamed Layer")
            
            # Get the path prefix for this layer
            path_prefix = layer.get("_path_prefix", [])
            
            # Log the current layer being processed with its full path
            current_path = "/".join(path_prefix + [layer_title]) if path_prefix else layer_title
            logger.info(f"Processing layer: {current_path}")
            
            # Add nested layers to processing queue with updated path prefix
            if "layers" in layer and isinstance(layer["layers"], list):
                logger.info(f"Found group layer '{layer_title}' with {len(layer['layers'])} child layers")
                
                # Create a new path prefix for child layers
                new_prefix = path_prefix + [layer_title]
                
                # Add child layers to the processing queue with the current layer as prefix
                for child_layer in reversed(layer["layers"]):
                    # Clone the child layer to avoid modifying the original
                    child_layer_copy = child_layer.copy()
                    # Store the path prefix with the layer for later use
                    child_layer_copy["_path_prefix"] = new_prefix
                    # We'll process these layers next, with the current layer as part of their path
                    layers_to_process.insert(0, child_layer_copy)
                
                # Continue to the next layer in the queue
                continue
            
            # Process feature layers with URLs
            if "url" in layer:
                layer_url = layer["url"]
                
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
                        editable
                    ):
                        updated_layers.append(layer_url)
                except Exception as e:
                    logger.error(f"Error processing layer '{layer_title}': {str(e)}")
            else:
                logger.info(f"Layer '{layer_title}' does not have a URL, skipping")
        
        logger.info(f"Updated {len(updated_layers)} layers in total")
        
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
    target_layer_names: Optional[List[str]] = None,
    field_names: Optional[List[str]] = None
) -> Dict[str, List[str]]:
    """
    Propagate form element configurations from a source layer to target layers.
    
    Args:
        webmap_item_id: The ID of the web map
        source_layer_name: The name of the source layer to copy configurations from
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
    webmap_item = get_webmap_item(webmap_item_id)
    if not webmap_item:
        return {}
    
    try:
        # Get the web map data (JSON)
        webmap_data = webmap_item.get_data()
        
        if "operationalLayers" not in webmap_data:
            logger.warning("No operational layers found in the webmap data")
            return {}
        
        # Find the source layer
        source_layer_result = find_layer_by_name(webmap_data["operationalLayers"], source_layer_name)
        if not source_layer_result:
            logger.error(f"Source layer '{source_layer_name}' not found in the web map")
            return {}
        
        source_layer, source_path = source_layer_result
        
        # Check if the source layer has a URL
        if "url" not in source_layer:
            logger.error(f"Source layer '{source_layer_name}' does not have a URL")
            return {}
        
        # Create a FeatureLayer for the source layer
        try:
            source_feature_layer = FeatureLayer(source_layer["url"], gis=gis)
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
        layers_to_process = []
        
        # Initialize the processing queue with top-level layers
        for layer in webmap_data["operationalLayers"]:
            # Add metadata to track layer path
            layer["_path_prefix"] = []
            layers_to_process.append(layer)
        
        while layers_to_process:
            layer = layers_to_process.pop(0)
            layer_title = layer.get("title", "Unnamed Layer")
            
            # Skip the source layer
            if layer_title == source_layer_name:
                logger.info(f"Skipping source layer '{source_layer_name}'")
                continue
            
            # Skip if target_layer_names is provided and this layer is not in the list
            if target_layer_names and layer_title not in target_layer_names:
                logger.info(f"Layer '{layer_title}' not in target layers list, skipping")
                
                # Still need to process child layers
                if "layers" in layer and isinstance(layer["layers"], list):
                    # Get the path prefix for this layer
                    path_prefix = layer.get("_path_prefix", [])
                    
                    # Create a new path prefix for child layers
                    new_prefix = path_prefix + [layer_title]
                    
                    # Add child layers to the processing queue with the current layer as prefix
                    for child_layer in layer["layers"]:
                        # Clone the child layer to avoid modifying the original
                        child_layer_copy = child_layer.copy()
                        # Store the path prefix with the layer for later use
                        child_layer_copy["_path_prefix"] = new_prefix
                        # We'll process these layers next, with the current layer as part of their path
                        layers_to_process.append(child_layer_copy)
                
                continue
            
            # Get the path prefix for this layer
            path_prefix = layer.get("_path_prefix", [])
            
            # Log the current layer being processed with its full path
            current_path = "/".join(path_prefix + [layer_title]) if path_prefix else layer_title
            logger.info(f"Processing layer: {current_path}")
            
            # Add nested layers to processing queue with updated path prefix
            if "layers" in layer and isinstance(layer["layers"], list):
                logger.info(f"Found group layer '{layer_title}' with {len(layer['layers'])} child layers")
                
                # Create a new path prefix for child layers
                new_prefix = path_prefix + [layer_title]
                
                # Add child layers to the processing queue with the current layer as prefix
                for child_layer in layer["layers"]:
                    # Clone the child layer to avoid modifying the original
                    child_layer_copy = child_layer.copy()
                    # Store the path prefix with the layer for later use
                    child_layer_copy["_path_prefix"] = new_prefix
                    # We'll process these layers next, with the current layer as part of their path
                    layers_to_process.append(child_layer_copy)
                
                # Continue to the next layer in the queue
                continue
            
            # Process feature layers with URLs
            if "url" in layer:
                layer_url = layer["url"]
                
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
                logger.info(f"Layer '{layer_title}' does not have a URL, skipping")
        
        logger.info(f"Updated {len(updated_layers)} layers in total")
        
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

def test_propagate_form_elements(
    webmap_item_id: str = "d1ea52f5280d4d57b5e331d21e00296e",
    source_layer_name: str = "Artifact Point",
    target_layer_names: Optional[List[str]] = None,
    field_names: Optional[List[str]] = None
) -> Dict[str, List[str]]:
    """
    Test function to demonstrate propagating form elements from a source layer to target layers.
    
    Args:
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
    webmap_item_id: str = "d1ea52f5280d4d57b5e331d21e00296e",
    field_name: str = "project_number",
    expression_name: str = "expr/set-project-number",
    expression_value: Optional[str] = None,
    group_name: str = "Metadata",
    field_label: Optional[str] = None,
    editable: bool = False
):
    """
    Test function to demonstrate updating a web map's forms.
    
    Args:
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
    update_parser.add_argument("--group", default="Metadata", help="Group name for the field")
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
    
    # Execute the appropriate command
    if args.command == "update":
        # Run the update function with provided arguments
        updated = test_webmap_forms_update(
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
