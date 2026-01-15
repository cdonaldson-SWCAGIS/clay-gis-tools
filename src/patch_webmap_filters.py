import json
import logging
import os
import random
import string
from typing import List, Optional, Dict, Any, Union

from arcgis.features import FeatureLayer
from arcgis.gis import GIS

from modules.logging_config import get_logger
from modules.webmap_utils import (
    get_webmap_item, layer_contains_field, process_webmap_layers,
    WebMapNotFoundError, InvalidWebMapError, LayerProcessingError
)
from modules.config import (
    OPERATIONAL_LAYERS_KEY, LAYER_DEFINITION_KEY, DEFINITION_EXPRESSION_KEY,
    URL_KEY, TITLE_KEY, UNNAMED_LAYER
)
from modules.exceptions import AuthenticationError

logger = get_logger("patch_webmap_filters")

# Global debug mode: Set to True to simulate updates (for testing) or False for production.
DEBUG_MODE = False

def generate_random_string(length: int = 8) -> str:
    """Generate a random alphanumeric string of specified length."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

# get_webmap_item and layer_contains_field are now imported from modules.webmap_utils

def capture_layer_state(layers: List[Dict], target_field: str, gis: GIS) -> Dict[str, Dict]:
    """
    Capture the current state of definition expressions for layers containing the target field.
    
    Args:
        layers: List of layer dictionaries
        target_field: The target field name
        gis: The authenticated GIS object
        
    Returns:
        Dictionary mapping layer URLs to their state information
    """
    layer_states = {}
    
    # Process all layers including nested ones
    for layer, _ in process_webmap_layers({OPERATIONAL_LAYERS_KEY: layers}):
        # Process feature layers with URLs
        if URL_KEY in layer:
            layer_url = layer[URL_KEY]
            try:
                # Create a FeatureLayer to examine its fields
                feature_layer = FeatureLayer(layer_url, gis=gis)
                if layer_contains_field(feature_layer, target_field):
                    # Only check for layerDefinition structure
                    definition_expression = None
                    if LAYER_DEFINITION_KEY in layer and DEFINITION_EXPRESSION_KEY in layer[LAYER_DEFINITION_KEY]:
                        definition_expression = layer[LAYER_DEFINITION_KEY][DEFINITION_EXPRESSION_KEY]
                    
                    layer_states[layer_url] = {
                        TITLE_KEY: layer.get(TITLE_KEY, UNNAMED_LAYER),
                        DEFINITION_EXPRESSION_KEY: definition_expression
                    }
            except Exception as e:
                logger.warning(f"Could not access layer {layer_url}: {e}")
                # Skip layers that can't be accessed
                pass
    
    return layer_states

def verify_webmap_changes(before_state: Dict, after_state: Dict, expected_filter: str) -> bool:
    """Verify that changes were actually made to the web map."""
    if not before_state:
        return False
    
    # Simple verification: at least one layer was updated correctly
    for layer_url, before in before_state.items():
        if layer_url in after_state:
            after = after_state[layer_url]
            if after["definitionExpression"] == expected_filter:
                return True
    
    return False

def update_webmap_definition_by_field(
    webmap_item_id: str,
    target_field: str,
    new_filter: str,
    gis: GIS,
    debug_mode: bool = False
) -> List[str]:
    """
    Update the definitionExpression for all layers in the web map that contain the target field.
    
    Args:
        webmap_item_id: The ID of the web map to update
        target_field: The field name to search for
        new_filter: The new filter expression to apply
        gis: The authenticated GIS object
        debug_mode: Whether to simulate updates without saving
        
    Returns:
        List of layer URLs that were updated
        
    Raises:
        WebMapNotFoundError: If the web map cannot be found
        InvalidWebMapError: If the web map is invalid
        LayerProcessingError: If layer processing fails
    """
    logger.info(f"Starting update process for web map {webmap_item_id}")
    logger.info(f"Target field: {target_field}")
    logger.info(f"New filter: {new_filter}")
    
    # Input validation
    if not webmap_item_id or not target_field or not new_filter:
        logger.error("Missing required parameters")
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
        
        # Capture the state before making changes
        before_state = capture_layer_state(webmap_data[OPERATIONAL_LAYERS_KEY], target_field, gis)
        logger.info(f"Found {len(before_state)} layers with target field '{target_field}'")
        
        # Process all layers including nested ones
        updated_layers = []
        
        for layer, _ in process_webmap_layers(webmap_data):
            # Process feature layers with URLs
            if URL_KEY in layer:
                layer_url = layer[URL_KEY]
                layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
                
                try:
                    # Create a FeatureLayer to examine its fields
                    feature_layer = FeatureLayer(layer_url, gis=gis)
                    if layer_contains_field(feature_layer, target_field):
                        # Ensure layerDefinition exists
                        if LAYER_DEFINITION_KEY not in layer:
                            layer[LAYER_DEFINITION_KEY] = {}
                        
                        # Update the definitionExpression in the layerDefinition
                        layer[LAYER_DEFINITION_KEY][DEFINITION_EXPRESSION_KEY] = new_filter
                        logger.info(f"Updated filter for layer '{layer_title}'")
                        updated_layers.append(layer_url)
                except Exception as e:
                    logger.error(f"Error processing layer '{layer_title}': {str(e)}")
        
        logger.info(f"Updated {len(updated_layers)} layers in total")
        
        # Save the changes to the web map
        if debug_mode or DEBUG_MODE:
            logger.info("DEBUG MODE: Webmap update simulated. Changes not saved to the server.")
            return updated_layers
        else:
            try:
                logger.info("Saving changes to web map...")
                update_result = webmap_item.update(data=webmap_data)
                
                if update_result:
                    logger.info("Webmap item update operation completed")
                    
                    # Simple verification
                    try:
                        updated_webmap_item = get_webmap_item(webmap_item_id, gis)
                        updated_webmap_data = updated_webmap_item.get_data()
                        after_state = capture_layer_state(updated_webmap_data[OPERATIONAL_LAYERS_KEY], target_field, gis)
                        
                        if verify_webmap_changes(before_state, after_state, new_filter):
                            logger.info(f"Changes verified: {len(updated_layers)} layers updated successfully")
                            return updated_layers
                        else:
                            logger.error("Changes verification failed")
                            return []
                    except (WebMapNotFoundError, InvalidWebMapError) as e:
                        logger.error(f"Failed to retrieve updated web map for verification: {e}")
                        return []
                else:
                    logger.error("Failed to update webmap item")
                    return []
            except Exception as e:
                logger.error(f"Error updating webmap item: {e}")
                return []
    except Exception as e:
        logger.error(f"Error in update process: {e}")
        raise LayerProcessingError(f"Error in update process: {e}") from e

def update_webmap_definitions_by_layer_config(
    webmap_item_id: str,
    layer_configs: Dict[str, Dict[str, str]],
    gis: GIS,
    debug_mode: bool = False
) -> Dict[str, Any]:
    """
    Update definition expressions for specific layers using per-layer configuration.
    
    Args:
        webmap_item_id: The ID of the web map to update
        layer_configs: Dictionary mapping layer URLs to their configuration:
            {
                "layer_url": {
                    "target_field": "field_name",
                    "filter_expression": "SQL WHERE clause"
                }
            }
        gis: The authenticated GIS object
        debug_mode: Whether to simulate updates without saving
        
    Returns:
        Dictionary with results:
            {
                "updated_layers": List of layer URLs that were updated,
                "skipped_layers": List of layer URLs that were skipped (field not found),
                "errors": Dict mapping layer URLs to error messages
            }
        
    Raises:
        WebMapNotFoundError: If the web map cannot be found
        InvalidWebMapError: If the web map is invalid
    """
    logger.info(f"Starting per-layer update process for web map {webmap_item_id}")
    logger.info(f"Processing {len(layer_configs)} layer configurations")
    
    result = {
        "updated_layers": [],
        "skipped_layers": [],
        "errors": {}
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
        
        # Process all layers including nested ones
        for layer, _ in process_webmap_layers(webmap_data):
            # Process feature layers with URLs
            if URL_KEY not in layer:
                continue
                
            layer_url = layer[URL_KEY]
            layer_title = layer.get(TITLE_KEY, UNNAMED_LAYER)
            
            # Check if this layer is in our config
            if layer_url not in layer_configs:
                continue
            
            config = layer_configs[layer_url]
            target_field = config.get("target_field", "")
            filter_expression = config.get("filter_expression", "")
            
            if not target_field or not filter_expression:
                logger.warning(f"Incomplete config for layer '{layer_title}': missing target_field or filter_expression")
                result["errors"][layer_url] = "Incomplete configuration"
                continue
            
            try:
                # Create a FeatureLayer to examine its fields
                feature_layer = FeatureLayer(layer_url, gis=gis)
                
                if layer_contains_field(feature_layer, target_field):
                    # Ensure layerDefinition exists
                    if LAYER_DEFINITION_KEY not in layer:
                        layer[LAYER_DEFINITION_KEY] = {}
                    
                    # Update the definitionExpression in the layerDefinition
                    layer[LAYER_DEFINITION_KEY][DEFINITION_EXPRESSION_KEY] = filter_expression
                    logger.info(f"Updated filter for layer '{layer_title}' on field '{target_field}'")
                    result["updated_layers"].append(layer_url)
                else:
                    logger.warning(f"Layer '{layer_title}' does not contain field '{target_field}'")
                    result["skipped_layers"].append(layer_url)
            except Exception as e:
                logger.error(f"Error processing layer '{layer_title}': {str(e)}")
                result["errors"][layer_url] = str(e)
        
        logger.info(f"Updated {len(result['updated_layers'])} layers, skipped {len(result['skipped_layers'])}, errors: {len(result['errors'])}")
        
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


def test_webmap_update(gis: GIS):
    """
    Test function to demonstrate updating a web map with a random filter.
    
    Args:
        gis: The authenticated GIS object
    """
    # Test parameters
    webmap_item_id = "3d7ba61233c744b997c9e275e8475254"
    target_field = "project_number"
    random_value = generate_random_string(8)
    new_filter = f"project_number = '{random_value}'"
    
    logger.info("=== Starting Web Map Update Test ===")
    logger.info(f"Using random filter value: {random_value}")
    
    # Perform the update
    updated_layers = update_webmap_definition_by_field(webmap_item_id, target_field, new_filter, gis, DEBUG_MODE)
    
    # Log results
    if updated_layers:
        logger.info(f"Successfully updated {len(updated_layers)} layers")
    else:
        logger.warning("No layers were updated")
    
    logger.info("=== Web Map Update Test Complete ===")
    return updated_layers

if __name__ == "__main__":
    import os
    from modules.authentication import authenticate_from_env
    
    # Set log level based on debug mode
    if DEBUG_MODE:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Get GIS connection - require environment variables
    try:
        gis = authenticate_from_env()
    except (ValueError, AuthenticationError) as e:
        logger.error(f"Authentication failed: {e}")
        logger.error("Please set ARCGIS_USERNAME, ARCGIS_PASSWORD, and optionally ARCGIS_PROFILE environment variables")
        sys.exit(1)
    
    # Example usage with random filter
    random_value = generate_random_string(8)
    webmap_item_id = "d1ea52f5280d4d57b5e331d21e00296e"
    target_field = "project_number"
    new_filter = f"project_number = 'foobar'"
    
    updated = update_webmap_definition_by_field(webmap_item_id, target_field, new_filter, gis, DEBUG_MODE)
    
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
        
        # If not in debug mode, provide more information about potential issues
        if not DEBUG_MODE:
            print("Possible issues:")
            print("  • The web map may not contain layers with the target field")
            print("  • The server may not have accepted the changes")
            print("  • There might be permission issues with the web map")
            print("\nTry running with DEBUG_MODE = True to see more details")
