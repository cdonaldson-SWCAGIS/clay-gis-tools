import json
import logging
import os
import random
import string
from typing import List, Optional, Dict, Any, Union

from arcgis.features import FeatureLayer
from arcgis.gis import GIS

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("patch_webmap_filters")

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

def capture_layer_state(layers: List[Dict], target_field: str) -> Dict[str, Dict]:
    """Capture the current state of definition expressions for layers containing the target field."""
    layer_states = {}
    
    # Process all layers including nested ones
    layers_to_process = layers.copy()
    while layers_to_process:
        layer = layers_to_process.pop(0)
        
        # Add nested layers to processing queue
        if "layers" in layer and isinstance(layer["layers"], list):
            layers_to_process.extend(layer["layers"])
        
        # Process feature layers with URLs
        if "url" in layer:
            layer_url = layer["url"]
            try:
                # Create a FeatureLayer to examine its fields
                feature_layer = FeatureLayer(layer_url, gis=gis)
                if layer_contains_field(feature_layer, target_field):
                    # Only check for layerDefinition structure
                    definition_expression = None
                    if "layerDefinition" in layer and "definitionExpression" in layer["layerDefinition"]:
                        definition_expression = layer["layerDefinition"]["definitionExpression"]
                    
                    layer_states[layer_url] = {
                        "title": layer.get("title", "Unnamed Layer"),
                        "definitionExpression": definition_expression
                    }
            except Exception:
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

def update_webmap_definition_by_field(webmap_item_id: str, target_field: str, new_filter: str) -> List[str]:
    """Update the definitionExpression for all layers in the web map that contain the target field."""
    logger.info(f"Starting update process for web map {webmap_item_id}")
    logger.info(f"Target field: {target_field}")
    logger.info(f"New filter: {new_filter}")
    
    # Input validation
    if not webmap_item_id or not target_field or not new_filter:
        logger.error("Missing required parameters")
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
        
        # Capture the state before making changes
        before_state = capture_layer_state(webmap_data["operationalLayers"], target_field)
        logger.info(f"Found {len(before_state)} layers with target field '{target_field}'")
        
        # Process all layers including nested ones
        updated_layers = []
        layers_to_process = webmap_data["operationalLayers"].copy()
        
        while layers_to_process:
            layer = layers_to_process.pop(0)
            
            # Add nested layers to processing queue
            if "layers" in layer and isinstance(layer["layers"], list):
                layers_to_process.extend(layer["layers"])
            
            # Process feature layers with URLs
            if "url" in layer:
                layer_url = layer["url"]
                layer_title = layer.get("title", "Unnamed Layer")
                
                try:
                    # Create a FeatureLayer to examine its fields
                    feature_layer = FeatureLayer(layer_url, gis=gis)
                    if layer_contains_field(feature_layer, target_field):
                        # Ensure layerDefinition exists
                        if "layerDefinition" not in layer:
                            layer["layerDefinition"] = {}
                        
                        # Update the definitionExpression in the layerDefinition
                        layer["layerDefinition"]["definitionExpression"] = new_filter
                        logger.info(f"Updated filter for layer '{layer_title}'")
                        updated_layers.append(layer_url)
                except Exception as e:
                    logger.error(f"Error processing layer '{layer_title}': {str(e)}")
        
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
                    logger.info("Webmap item update operation completed")
                    
                    # Simple verification
                    updated_webmap_item = get_webmap_item(webmap_item_id)
                    if updated_webmap_item:
                        updated_webmap_data = updated_webmap_item.get_data()
                        after_state = capture_layer_state(updated_webmap_data["operationalLayers"], target_field)
                        
                        if verify_webmap_changes(before_state, after_state, new_filter):
                            logger.info(f"Changes verified: {len(updated_layers)} layers updated successfully")
                            return updated_layers
                        else:
                            logger.error("Changes verification failed")
                            return []
                    else:
                        logger.error("Failed to retrieve updated web map for verification")
                        return []
                else:
                    logger.error("Failed to update webmap item")
                    return []
            except Exception as e:
                logger.error(f"Error updating webmap item: {e}")
                return []
    except Exception as e:
        logger.error(f"Error in update process: {e}")
        return []

def test_webmap_update():
    """Test function to demonstrate updating a web map with a random filter."""
    # Test parameters
    webmap_item_id = "3d7ba61233c744b997c9e275e8475254"
    target_field = "project_number"
    random_value = generate_random_string(8)
    new_filter = f"project_number = '{random_value}'"
    
    logger.info("=== Starting Web Map Update Test ===")
    logger.info(f"Using random filter value: {random_value}")
    
    # Perform the update
    updated_layers = update_webmap_definition_by_field(webmap_item_id, target_field, new_filter)
    
    # Log results
    if updated_layers:
        logger.info(f"Successfully updated {len(updated_layers)} layers")
    else:
        logger.warning("No layers were updated")
    
    logger.info("=== Web Map Update Test Complete ===")
    return updated_layers

if __name__ == "__main__":
    # Set log level based on debug mode
    if DEBUG_MODE:
        logger.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Example usage with random filter
    random_value = generate_random_string(8)
    webmap_item_id = "d1ea52f5280d4d57b5e331d21e00296e"
    target_field = "project_number"
    new_filter = f"project_number = 'foobar'"
    
    updated = update_webmap_definition_by_field(webmap_item_id, target_field, new_filter)
    
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
