"""
Shared utilities for web map operations.
Provides common functions used across web map manipulation modules.
No Streamlit dependencies - pure backend logic.
"""

import logging
from typing import Optional, Dict, Any, Generator, Tuple, List
from arcgis.gis import GIS
from arcgis.features import FeatureLayer
from arcgis.gis import Item

from backend.utils.config import OPERATIONAL_LAYERS_KEY, URL_KEY, LAYERS_KEY, TITLE_KEY, UNNAMED_LAYER
from backend.utils.exceptions import WebMapNotFoundError, InvalidWebMapError, LayerProcessingError
from backend.utils.logging import get_logger

logger = get_logger("webmap_utils")


def get_webmap_item(webmap_item_id: str, gis: GIS) -> Item:
    """
    Retrieve a web map item using the provided GIS object.
    
    Args:
        webmap_item_id: The ID of the web map to retrieve
        gis: The authenticated GIS object
        
    Returns:
        Web map Item object
        
    Raises:
        WebMapNotFoundError: If the web map is not found
        InvalidWebMapError: If the item is not a web map or is inaccessible
    """
    if not webmap_item_id or not isinstance(webmap_item_id, str):
        raise InvalidWebMapError("Invalid webmap_item_id provided")
    
    try:
        logger.info(f"Retrieving web map with ID: {webmap_item_id}")
        webmap_item = gis.content.get(webmap_item_id)
        
        if not webmap_item:
            raise WebMapNotFoundError(f"Web map with ID {webmap_item_id} was not found")
        
        if webmap_item.type != "Web Map":
            raise InvalidWebMapError(f"Item {webmap_item_id} is not a Web Map (found: {webmap_item.type})")
        
        logger.debug(f"Successfully retrieved web map: {webmap_item.title}")
        return webmap_item
        
    except (WebMapNotFoundError, InvalidWebMapError):
        raise
    except Exception as e:
        logger.error(f"Error retrieving web map: {e}")
        raise InvalidWebMapError(f"Error retrieving web map: {e}") from e


def layer_contains_field(feature_layer: FeatureLayer, target_field: str) -> bool:
    """
    Check if a feature layer contains the target field.
    
    Args:
        feature_layer: The FeatureLayer object to check
        target_field: The name of the field to look for
        
    Returns:
        True if the field exists, False otherwise
    """
    if not feature_layer or not target_field:
        return False
    
    try:
        fields = feature_layer.properties.fields
        return any(field.get("name") == target_field for field in fields)
    except Exception as e:
        logger.warning(f"Error checking fields in layer: {e}")
        return False


def process_webmap_layers(
    webmap_data: Dict[str, Any],
    include_path: bool = False
) -> Generator[Tuple[Dict[str, Any], List[str]], None, None]:
    """
    Generator function to recursively process all layers in a web map.
    
    Args:
        webmap_data: The web map data dictionary
        include_path: Whether to include the layer path in the result
        
    Yields:
        Tuple of (layer_dict, path_list) where path_list is empty if include_path=False
    """
    if OPERATIONAL_LAYERS_KEY not in webmap_data:
        logger.warning("No operational layers found in the webmap data")
        return
    
    layers_to_process = []
    
    # Initialize the processing queue with top-level layers
    for layer in webmap_data[OPERATIONAL_LAYERS_KEY]:
        layer_copy = layer.copy()
        if include_path:
            layer_copy["_path_prefix"] = []
        layers_to_process.append(layer_copy)
    
    while layers_to_process:
        layer = layers_to_process.pop(0)
        
        # Get the path prefix for this layer if tracking paths
        path_prefix = layer.get("_path_prefix", []) if include_path else []
        
        # Add nested layers to processing queue
        if LAYERS_KEY in layer and isinstance(layer[LAYERS_KEY], list):
            new_prefix = path_prefix + [layer.get(TITLE_KEY, UNNAMED_LAYER)] if include_path else []
            
            for child_layer in layer[LAYERS_KEY]:
                child_layer_copy = child_layer.copy()
                if include_path:
                    child_layer_copy["_path_prefix"] = new_prefix
                layers_to_process.append(child_layer_copy)
        
        # Yield the layer (it might be a group layer or feature layer)
        yield (layer, path_prefix)


def get_layer_path_string(layer: Dict[str, Any], path_prefix: List[str]) -> str:
    """
    Get a string representation of a layer's path.
    
    Args:
        layer: The layer dictionary
        path_prefix: The path prefix list
        
    Returns:
        String representation of the layer path
    """
    layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
    if path_prefix:
        return "/".join(path_prefix + [layer_title])
    return layer_title


def get_layer_fields(layer_url: str, gis: GIS) -> List[str]:
    """
    Get the list of field names from a feature layer.
    
    Args:
        layer_url: The URL of the feature layer
        gis: The authenticated GIS object
        
    Returns:
        List of field names, or empty list if unable to fetch
    """
    try:
        feature_layer = FeatureLayer(layer_url, gis=gis)
        fields = feature_layer.properties.fields
        return [field.get("name") for field in fields if field.get("name")]
    except Exception as e:
        logger.warning(f"Could not fetch fields for layer {layer_url}: {e}")
        return []


def get_layer_fields_with_types(layer_url: str, gis: GIS) -> List[Dict[str, Any]]:
    """
    Get the list of fields with type information from a feature layer.
    
    Args:
        layer_url: The URL of the feature layer
        gis: The authenticated GIS object
        
    Returns:
        List of field dictionaries with name and type, or empty list if unable to fetch
    """
    try:
        feature_layer = FeatureLayer(layer_url, gis=gis)
        fields = feature_layer.properties.fields
        return [
            {
                "name": field.get("name"),
                "type": field.get("type", "Unknown"),
                "alias": field.get("alias", field.get("name", ""))
            }
            for field in fields 
            if field.get("name")
        ]
    except Exception as e:
        logger.warning(f"Could not fetch fields for layer {layer_url}: {e}")
        return []


def get_webmap_layer_details(webmap_item: Item, gis: GIS) -> List[Dict[str, Any]]:
    """
    Get detailed information about all layers in a web map.
    
    Iterates through operational layers (including nested group layers) and returns
    a list of layer details including URL, name, path, and available fields.
    
    Args:
        webmap_item: The web map Item object
        gis: The authenticated GIS object
        
    Returns:
        List of dictionaries containing layer details:
        - url: The layer URL
        - id: A unique identifier (the URL)
        - name: The layer title/name
        - path: Full path including parent groups (e.g., "GroupName/LayerName")
        - fields: List of field names available in the layer
        - has_form_info: Whether the layer has form configuration
    """
    layer_details = []
    
    try:
        webmap_data = webmap_item.get_data()
    except Exception as e:
        logger.error(f"Failed to get web map data: {e}")
        return layer_details
    
    if OPERATIONAL_LAYERS_KEY not in webmap_data:
        logger.warning("No operational layers found in the web map")
        return layer_details
    
    # Process all layers including nested ones
    for layer, path_prefix in process_webmap_layers(webmap_data, include_path=True):
        # Only process layers with URLs (feature layers, not group layers)
        if URL_KEY not in layer:
            continue
        
        layer_url = layer[URL_KEY]
        layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
        layer_path = get_layer_path_string(layer, path_prefix)
        
        # Fetch fields for this layer (with type information)
        fields_with_types = get_layer_fields_with_types(layer_url, gis)
        # Also keep field names for backward compatibility
        field_names = [f["name"] for f in fields_with_types]
        
        # Check if layer has form info
        has_form_info = "formInfo" in layer and "formElements" in layer.get("formInfo", {})
        
        layer_details.append({
            "url": layer_url,
            "id": layer_url,  # Using URL as unique identifier
            "name": layer_title,
            "path": layer_path,
            "fields": field_names,  # Keep for backward compatibility
            "fields_with_types": fields_with_types,  # New: fields with type info
            "has_form_info": has_form_info
        })
        
        logger.debug(f"Processed layer: {layer_path} with {len(field_names)} fields")
    
    logger.info(f"Found {len(layer_details)} feature layers in web map")
    return layer_details


def get_all_unique_fields(layer_details: List[Dict[str, Any]]) -> List[str]:
    """
    Get a sorted list of all unique field names across all layers.
    
    Args:
        layer_details: List of layer detail dictionaries from get_webmap_layer_details
        
    Returns:
        Sorted list of unique field names
    """
    all_fields = set()
    for layer in layer_details:
        all_fields.update(layer.get("fields", []))
    return sorted(all_fields)


def get_feature_layer(gis: GIS, layer_url: str) -> Optional[FeatureLayer]:
    """
    Create a FeatureLayer object with error handling.
    
    Args:
        gis: The authenticated GIS object
        layer_url: The URL of the feature layer
        
    Returns:
        FeatureLayer object or None if creation fails
    """
    if not layer_url:
        logger.error("Invalid layer_url provided")
        return None
    
    try:
        logger.debug(f"Creating FeatureLayer for URL: {layer_url}")
        feature_layer = FeatureLayer(layer_url, gis=gis)
        return feature_layer
        
    except Exception as e:
        logger.error(f"Error creating FeatureLayer for {layer_url}: {e}")
        return None


def get_layer_fields_from_feature_layer(feature_layer: FeatureLayer) -> List[Dict[str, Any]]:
    """
    Get the list of fields from a feature layer.
    
    Args:
        feature_layer: The FeatureLayer object
        
    Returns:
        List of field dictionaries
    """
    if not feature_layer:
        return []
    
    try:
        return feature_layer.properties.fields
    except Exception as e:
        logger.error(f"Error getting fields from layer: {e}")
        return []


def find_layers_with_field(webmap_data: Dict[str, Any], gis: GIS, target_field: str) -> List[Dict[str, Any]]:
    """
    Find all layers in a web map that contain a specific field.
    
    Args:
        webmap_data: The web map JSON data
        gis: The authenticated GIS object
        target_field: The name of the field to search for
        
    Returns:
        List of layer dictionaries that contain the target field
    """
    matching_layers = []
    
    if OPERATIONAL_LAYERS_KEY not in webmap_data:
        logger.warning("No operational layers found in the webmap data")
        return matching_layers
    
    # Process all layers including nested ones
    layers_to_process = webmap_data[OPERATIONAL_LAYERS_KEY].copy()
    
    while layers_to_process:
        layer = layers_to_process.pop(0)
        
        # Add nested layers to processing queue
        if LAYERS_KEY in layer and isinstance(layer[LAYERS_KEY], list):
            layers_to_process.extend(layer[LAYERS_KEY])
        
        # Process feature layers with URLs
        if URL_KEY in layer:
            feature_layer = get_feature_layer(gis, layer[URL_KEY])
            if feature_layer and layer_contains_field(feature_layer, target_field):
                matching_layers.append(layer)
                logger.debug(f"Found layer with field '{target_field}': {layer.get(TITLE_KEY, UNNAMED_LAYER)}")
    
    logger.info(f"Found {len(matching_layers)} layers with field '{target_field}'")
    return matching_layers
