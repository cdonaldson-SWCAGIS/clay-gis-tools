"""
Shared utilities for web map operations.
Provides common functions used across web map manipulation modules.
No Streamlit dependencies - pure backend logic.
"""

import logging
import os
from typing import Optional, Dict, Any, Generator, Tuple, List
from arcgis.gis import GIS
from arcgis.features import FeatureLayer
from arcgis.gis import Item
from arcgis.map import Map

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
        # Esri returns nested layers in reverse order, so reverse them to match webmap display order
        if LAYERS_KEY in layer and isinstance(layer[LAYERS_KEY], list):
            new_prefix = path_prefix + [layer.get(TITLE_KEY, UNNAMED_LAYER)] if include_path else []
            
            # Reverse nested layers to match webmap display order
            nested_layers = list(reversed(layer[LAYERS_KEY]))
            for child_layer in nested_layers:
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
    
    Forms can exist in two places:
    1. In the webmap's layer configuration (webmap form)
    2. On the layer item itself (layer form)
    
    The webmap form takes precedence when both exist. A layer is considered to
    have a form if EITHER source has one.
    
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
        - fields_with_types: List of field dicts with name and type
        - has_form_info: Whether the layer has form configuration (from either source)
        - has_webmap_form: Whether the webmap has form config for this layer
        - has_layer_form: Whether the layer item has form config
        - form_source: "webmap", "layer", or "none"
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
    
    # Esri returns operational layers in reverse order, so reverse them to match webmap display order
    webmap_data_copy = webmap_data.copy()
    if OPERATIONAL_LAYERS_KEY in webmap_data_copy:
        webmap_data_copy[OPERATIONAL_LAYERS_KEY] = list(reversed(webmap_data_copy[OPERATIONAL_LAYERS_KEY]))
    
    # Process all layers including nested ones
    for layer, path_prefix in process_webmap_layers(webmap_data_copy, include_path=True):
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
        
        # Check if webmap has form info for this layer
        has_webmap_form = "formInfo" in layer and "formElements" in layer.get("formInfo", {})
        
        # Check if layer item has form info
        has_layer_form = False
        try:
            feature_layer = FeatureLayer(layer_url, gis=gis)
            layer_form_info = get_layer_item_form_info(feature_layer, gis)
            has_layer_form = layer_form_info is not None and "formElements" in layer_form_info
        except Exception as e:
            logger.debug(f"Could not check layer item form for '{layer_title}': {e}")
        
        # Determine form source (webmap takes precedence)
        if has_webmap_form:
            form_source = "webmap"
        elif has_layer_form:
            form_source = "layer"
        else:
            form_source = "none"
        
        # has_form_info is True if EITHER source has a form
        has_form_info = has_webmap_form or has_layer_form
        
        layer_details.append({
            "url": layer_url,
            "id": layer_url,  # Using URL as unique identifier
            "name": layer_title,
            "path": layer_path,
            "fields": field_names,  # Keep for backward compatibility
            "fields_with_types": fields_with_types,  # New: fields with type info
            "has_form_info": has_form_info,
            "has_webmap_form": has_webmap_form,
            "has_layer_form": has_layer_form,
            "form_source": form_source
        })
        
        logger.debug(f"Processed layer: {layer_path} with {len(field_names)} fields, form_source={form_source}")
    
    logger.info(f"Found {len(layer_details)} feature layers in web map")
    return layer_details


def get_layer_item_form_info(
    feature_layer: FeatureLayer,
    gis: GIS,
    layer_index: Optional[int] = None
) -> Optional[Dict[str, Any]]:
    """
    Get formInfo from a layer's source item (Feature Layer item).
    
    Forms can be saved either to the web map (layer config) or to the layer item itself.
    This function retrieves the form from the layer item if it exists.
    
    Args:
        feature_layer: The FeatureLayer object
        gis: The authenticated GIS object
        layer_index: Optional layer index within the service (extracted from URL if not provided)
        
    Returns:
        formInfo dictionary if found, None otherwise
    """
    if not feature_layer:
        return None
    
    try:
        # Get the service item ID from the feature layer properties
        service_item_id = feature_layer.properties.get("serviceItemId")
        
        if not service_item_id:
            logger.debug("No serviceItemId found on feature layer")
            return None
        
        # Fetch the layer item
        layer_item = gis.content.get(service_item_id)
        if not layer_item:
            logger.debug(f"Could not fetch layer item with ID: {service_item_id}")
            return None
        
        # Get the item's data
        item_data = layer_item.get_data()
        if not item_data:
            logger.debug(f"No data found for layer item: {service_item_id}")
            return None
        
        # Determine layer index from URL if not provided
        if layer_index is None:
            try:
                # Extract layer index from URL (e.g., .../FeatureServer/0)
                url = feature_layer.url
                if url and "/FeatureServer/" in url:
                    layer_index = int(url.split("/FeatureServer/")[-1].split("/")[0])
                elif url and "/MapServer/" in url:
                    layer_index = int(url.split("/MapServer/")[-1].split("/")[0])
            except (ValueError, IndexError):
                layer_index = 0
        
        def _merge_expressions(form_info: Dict, parent_expressions: List) -> None:
            """Merge parent-level expressions into formInfo, avoiding duplicates."""
            if not parent_expressions:
                return
            
            if "expressionInfos" not in form_info:
                form_info["expressionInfos"] = []
            
            # Get existing expression names
            existing_names = {e.get("name") for e in form_info["expressionInfos"]}
            
            # Add parent expressions that don't already exist
            for expr in parent_expressions:
                if expr.get("name") and expr.get("name") not in existing_names:
                    form_info["expressionInfos"].append(expr)
        
        # Check for formInfo in the item data
        # It can be at the top level or within a layers array
        # Also capture expressionInfos which may be at the layer level (not inside formInfo)
        
        if "formInfo" in item_data:
            logger.debug(f"Found formInfo at top level of layer item: {service_item_id}")
            form_info = item_data["formInfo"].copy()
            # Deep copy expressionInfos if present
            if "expressionInfos" in form_info:
                form_info["expressionInfos"] = [e.copy() for e in form_info["expressionInfos"]]
            # Also merge expressionInfos from top level
            _merge_expressions(form_info, item_data.get("expressionInfos", []))
            return form_info
        
        # Check in layers array (for Feature Layer Collection items)
        if "layers" in item_data and isinstance(item_data["layers"], list):
            for layer_data in item_data["layers"]:
                # Match by layer index/id
                layer_id = layer_data.get("id")
                if layer_id == layer_index or layer_id == str(layer_index):
                    if "formInfo" in layer_data:
                        logger.debug(f"Found formInfo in layer {layer_index} of item: {service_item_id}")
                        form_info = layer_data["formInfo"].copy()
                        # Deep copy expressionInfos if present
                        if "expressionInfos" in form_info:
                            form_info["expressionInfos"] = [e.copy() for e in form_info["expressionInfos"]]
                        # Also merge expressionInfos from layer level and top level
                        _merge_expressions(form_info, layer_data.get("expressionInfos", []))
                        _merge_expressions(form_info, item_data.get("expressionInfos", []))
                        return form_info
        
        # Check in tables array as well
        if "tables" in item_data and isinstance(item_data["tables"], list):
            for table_data in item_data["tables"]:
                table_id = table_data.get("id")
                if table_id == layer_index or table_id == str(layer_index):
                    if "formInfo" in table_data:
                        logger.debug(f"Found formInfo in table {layer_index} of item: {service_item_id}")
                        form_info = table_data["formInfo"].copy()
                        # Deep copy expressionInfos if present
                        if "expressionInfos" in form_info:
                            form_info["expressionInfos"] = [e.copy() for e in form_info["expressionInfos"]]
                        # Also merge expressionInfos from table level and top level
                        _merge_expressions(form_info, table_data.get("expressionInfos", []))
                        _merge_expressions(form_info, item_data.get("expressionInfos", []))
                        return form_info
        
        logger.debug(f"No formInfo found in layer item: {service_item_id}")
        return None
        
    except Exception as e:
        logger.warning(f"Error fetching layer item formInfo: {e}")
        return None


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


def get_portal_url(gis: GIS) -> str:
    """
    Get the portal URL for the authenticated user.
    
    Args:
        gis: Authenticated GIS object
        
    Returns:
        Portal URL string (without trailing slash)
    """
    # Try multiple methods to get portal URL
    if hasattr(gis, 'url') and gis.url:
        portal_url = gis.url
    elif hasattr(gis, 'properties') and hasattr(gis.properties, 'url') and gis.properties.url:
        portal_url = gis.properties.url
    else:
        # Fallback: default to ArcGIS Online
        portal_url = "https://www.arcgis.com"
        logger.warning("Could not determine portal URL, defaulting to ArcGIS Online")
    
    # Ensure URL doesn't end with slash
    return portal_url.rstrip('/')


def copy_webmap_as_new(
    source_webmap_id: str,
    gis: GIS,
    new_title: Optional[str] = None,
    map_suffix: Optional[str] = None,
    debug_mode: bool = False
) -> Dict[str, Any]:
    """
    Create a copy of a web map with a new title using the Map.save() method.
    
    Args:
        source_webmap_id: ID of the source web map to copy
        gis: Authenticated GIS object
        new_title: Custom title for the new web map (if None, uses <original>_<suffix>)
        map_suffix: Suffix to append to title (if None, uses MAP_SUFFIX env var)
        debug_mode: If True, simulate the operation without creating the map
        
    Returns:
        Dictionary containing:
        - success: bool
        - new_webmap_id: str (if successful)
        - new_webmap_title: str
        - portal_url: str (link to the new web map)
        - message: str
        - source_webmap_title: str (for reference)
    """
    try:
        # Get source web map
        source_item = get_webmap_item(source_webmap_id, gis)
        
        # Determine new title
        if not new_title:
            # Get suffix from parameter or environment variable
            if map_suffix is None:
                map_suffix = os.environ.get("MAP_SUFFIX", "_Copy")
            new_title = f"{source_item.title}{map_suffix}"
        
        if debug_mode:
            logger.info(f"DEBUG MODE: Would create web map '{new_title}'")
            portal_url = get_portal_url(gis)
            return {
                "success": True,
                "new_webmap_id": None,
                "new_webmap_title": new_title,
                "portal_url": None,
                "message": f"DEBUG: Would create web map '{new_title}'",
                "source_webmap_title": source_item.title
            }
        
        # Create Map object and save as new
        logger.info(f"Creating copy of web map '{source_item.title}' as '{new_title}'")
        map_obj = Map(source_item)
        
        item_props = {
            "title": new_title,
            "snippet": source_item.description or f"Copy of {source_item.title}",
            "tags": (source_item.tags or []) + ["copied", "save_as_new"]
        }
        
        new_item = map_obj.save(item_props)
        
        # Get portal URL and construct link
        portal_url = get_portal_url(gis)
        item_url = f"{portal_url}/home/item.html?id={new_item.id}"
        
        logger.info(f"Successfully created web map '{new_title}' with ID: {new_item.id}")
        
        return {
            "success": True,
            "new_webmap_id": new_item.id,
            "new_webmap_title": new_item.title,
            "portal_url": item_url,
            "message": f"Successfully created web map '{new_title}'",
            "source_webmap_title": source_item.title
        }
        
    except (WebMapNotFoundError, InvalidWebMapError) as e:
        logger.error(f"Error copying web map: {e}")
        return {
            "success": False,
            "new_webmap_id": None,
            "new_webmap_title": None,
            "portal_url": None,
            "message": f"Error: {str(e)}",
            "source_webmap_title": None
        }
    except Exception as e:
        logger.error(f"Unexpected error copying web map: {e}")
        return {
            "success": False,
            "new_webmap_id": None,
            "new_webmap_title": None,
            "portal_url": None,
            "message": f"Unexpected error: {str(e)}",
            "source_webmap_title": None
        }


def layer_has_attachments(feature_layer: FeatureLayer) -> bool:
    """
    Check if a feature layer has attachments enabled.
    
    Args:
        feature_layer: The FeatureLayer object to check
        
    Returns:
        True if the layer has attachments enabled, False otherwise
    """
    if not feature_layer:
        return False
    
    try:
        # Check the hasAttachments property
        has_attachments = feature_layer.properties.get("hasAttachments", False)
        return bool(has_attachments)
    except Exception as e:
        logger.warning(f"Error checking attachments for layer: {e}")
        return False


def get_layer_attachments(
    feature_layer: FeatureLayer,
    object_ids: List[int]
) -> Dict[int, List[Dict[str, Any]]]:
    """
    Get attachments for specific features in a layer.
    
    Args:
        feature_layer: The FeatureLayer object
        object_ids: List of object IDs to get attachments for
        
    Returns:
        Dictionary mapping object IDs to lists of attachment info dictionaries.
        Each attachment dict contains: id, name, contentType, size, etc.
    """
    if not feature_layer or not object_ids:
        return {}
    
    attachments_by_oid = {}
    
    try:
        # Check if layer has attachments enabled
        if not layer_has_attachments(feature_layer):
            logger.debug("Layer does not have attachments enabled")
            return {}
        
        # Get attachment manager
        attachment_manager = feature_layer.attachments
        
        # Query attachments for each object ID
        for oid in object_ids:
            try:
                attachments = attachment_manager.get_list(oid)
                if attachments:
                    attachments_by_oid[oid] = attachments
                    logger.debug(f"Found {len(attachments)} attachments for OID {oid}")
            except Exception as e:
                logger.warning(f"Error getting attachments for OID {oid}: {e}")
                attachments_by_oid[oid] = []
        
        return attachments_by_oid
        
    except Exception as e:
        logger.error(f"Error getting attachments: {e}")
        return {}


def query_features_by_field(
    layer_url: str,
    match_field: str,
    gis: GIS,
    where_clause: str = "1=1"
) -> List[Dict[str, Any]]:
    """
    Query features from a layer and return specified field values along with feature info.
    
    Args:
        layer_url: The URL of the feature layer
        match_field: The field name to retrieve values for
        gis: The authenticated GIS object
        where_clause: Optional SQL where clause to filter features
        
    Returns:
        List of dictionaries containing feature info:
        - object_id: The feature's object ID
        - global_id: The feature's global ID (if available)
        - match_value: The value of the match field
        - layer_url: The layer URL for reference
    """
    features = []
    
    try:
        feature_layer = FeatureLayer(layer_url, gis=gis)
        
        # Get the ObjectID and GlobalID field names from layer properties
        object_id_field = feature_layer.properties.get("objectIdField", "OBJECTID")
        global_id_field = feature_layer.properties.get("globalIdField", "GlobalID")
        
        # Build out_fields list - include match field, OID, and GlobalID
        out_fields = [match_field, object_id_field]
        if global_id_field and global_id_field != object_id_field:
            out_fields.append(global_id_field)
        
        # Query features
        result = feature_layer.query(
            where=where_clause,
            out_fields=",".join(out_fields),
            return_geometry=False
        )
        
        for f in result.features:
            attrs = f.attributes
            match_value = attrs.get(match_field)
            
            # Skip features with null/empty match values
            if match_value is None or match_value == "":
                continue
            
            features.append({
                "object_id": attrs.get(object_id_field),
                "global_id": attrs.get(global_id_field, ""),
                "match_value": match_value,
                "layer_url": layer_url
            })
        
        logger.info(f"Queried {len(features)} features from layer with match field '{match_field}'")
        return features
        
    except Exception as e:
        logger.error(f"Error querying features from {layer_url}: {e}")
        return []


def get_webmap_layer_details_with_attachments(
    webmap_item: Item,
    gis: GIS
) -> List[Dict[str, Any]]:
    """
    Get detailed information about layers in a web map, filtered to only include
    layers that have attachments enabled.
    
    Args:
        webmap_item: The web map Item object
        gis: The authenticated GIS object
        
    Returns:
        List of layer detail dictionaries (same structure as get_webmap_layer_details)
        but only including layers with attachments enabled.
    """
    # Get all layer details first
    all_layers = get_webmap_layer_details(webmap_item, gis)
    
    # Filter to layers with attachments
    layers_with_attachments = []
    for layer in all_layers:
        try:
            feature_layer = FeatureLayer(layer["url"], gis=gis)
            if layer_has_attachments(feature_layer):
                layer["has_attachments"] = True
                layers_with_attachments.append(layer)
                logger.debug(f"Layer '{layer['name']}' has attachments enabled")
        except Exception as e:
            logger.warning(f"Error checking attachments for layer '{layer['name']}': {e}")
    
    logger.info(f"Found {len(layers_with_attachments)} layers with attachments out of {len(all_layers)} total")
    return layers_with_attachments