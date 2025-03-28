import json
import logging
import unittest
from unittest.mock import patch, MagicMock

# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_patch_webmap_filters")

# Import the module to test
from patch_webmap_filters import (
    update_webmap_definition_by_field,
    capture_layer_state,
    verify_webmap_changes,
    layer_contains_field,
    get_webmap_item
)

class MockFeatureLayer:
    """Mock FeatureLayer for testing"""
    def __init__(self, url, fields=None):
        self.url = url
        self.properties = MagicMock()
        self.properties.fields = fields or [{"name": "project_number"}]

class TestPatchWebmapFilters(unittest.TestCase):
    """Test cases for patch_webmap_filters.py"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock GIS object
        self.mock_gis = MagicMock()
        
        # Mock webmap item
        self.mock_webmap_item = MagicMock()
        self.mock_webmap_item.title = "Test Web Map"
        
        # Test data
        self.webmap_item_id = "test_webmap_id"
        self.target_field = "project_number"
        self.new_filter = "project_number = 'TEST123'"
        
        # Create test layers with different definitionExpression configurations
        self.test_layers = self._create_test_layers()
        
        # Create mock webmap data
        self.mock_webmap_data = {
            "operationalLayers": self.test_layers
        }
        
        # Configure mock webmap item to return mock data
        self.mock_webmap_item.get_data.return_value = self.mock_webmap_data
        
        # Configure mock GIS to return mock webmap item
        self.mock_gis.content.get.return_value = self.mock_webmap_item
    
    def _create_test_layers(self):
        """Create test layers with different definitionExpression configurations"""
        return [
            # Case 1: No definitionExpression at all
            {
                "url": "https://services.arcgis.com/layer1",
                "title": "Layer with no definitionExpression"
            },
            
            # Case 2: Empty definitionExpression
            {
                "url": "https://services.arcgis.com/layer2",
                "title": "Layer with empty definitionExpression",
                "definitionExpression": ""
            },
            
            # Case 3: Top-level definitionExpression
            {
                "url": "https://services.arcgis.com/layer3",
                "title": "Layer with top-level definitionExpression",
                "definitionExpression": "status = 'ACTIVE'"
            },
            
            # Case 4: layerDefinition with no definitionExpression
            {
                "url": "https://services.arcgis.com/layer4",
                "title": "Layer with layerDefinition but no definitionExpression",
                "layerDefinition": {
                    "minScale": 0,
                    "maxScale": 0
                }
            },
            
            # Case 5: layerDefinition with definitionExpression
            {
                "url": "https://services.arcgis.com/layer5",
                "title": "Layer with layerDefinition and definitionExpression",
                "layerDefinition": {
                    "definitionExpression": "status = 'PENDING'",
                    "minScale": 0,
                    "maxScale": 0
                }
            },
            
            # Case 6: Both top-level and layerDefinition definitionExpression
            {
                "url": "https://services.arcgis.com/layer6",
                "title": "Layer with both definitionExpression locations",
                "definitionExpression": "status = 'LEGACY'",
                "layerDefinition": {
                    "definitionExpression": "status = 'CURRENT'",
                    "minScale": 0,
                    "maxScale": 0
                }
            },
            
            # Case 7: Nested group layer with feature layers
            {
                "title": "Group Layer",
                "layers": [
                    {
                        "url": "https://services.arcgis.com/layer7",
                        "title": "Nested layer with no definitionExpression"
                    },
                    {
                        "url": "https://services.arcgis.com/layer8",
                        "title": "Nested layer with layerDefinition",
                        "layerDefinition": {
                            "definitionExpression": "status = 'NESTED'"
                        }
                    }
                ]
            }
        ]
    
    @patch('patch_webmap_filters.gis')
    @patch('patch_webmap_filters.FeatureLayer')
    def test_capture_layer_state(self, mock_feature_layer_class, mock_gis):
        """Test capture_layer_state function with different layer configurations"""
        # Configure mocks
        mock_gis.return_value = self.mock_gis
        
        # Create mock feature layers for each URL
        mock_feature_layers = {}
        for layer in self.test_layers:
            if "url" in layer:
                url = layer["url"]
                mock_feature_layers[url] = MockFeatureLayer(url)
            elif "layers" in layer:
                for nested_layer in layer["layers"]:
                    if "url" in nested_layer:
                        url = nested_layer["url"]
                        mock_feature_layers[url] = MockFeatureLayer(url)
        
        # Configure mock_feature_layer_class to return appropriate mock feature layer
        mock_feature_layer_class.side_effect = lambda url, gis: mock_feature_layers.get(url)
        
        # Mock layer_contains_field to always return True for testing
        with patch('patch_webmap_filters.layer_contains_field', return_value=True):
            # Call the function
            result = capture_layer_state(self.test_layers, self.target_field)
            
            # Verify results
            self.assertEqual(len(result), 8, "Should capture state for all 8 feature layers")
            
            # Check specific cases
            self.assertIsNone(result["https://services.arcgis.com/layer1"]["definitionExpression"], 
                             "Layer with no definitionExpression should have None")
            
            self.assertIsNone(result["https://services.arcgis.com/layer2"]["definitionExpression"], 
                            "Layer with only top-level definitionExpression should have None")
            
            self.assertIsNone(result["https://services.arcgis.com/layer3"]["definitionExpression"], 
                            "Layer with only top-level definitionExpression should have None")
            
            self.assertIsNone(result["https://services.arcgis.com/layer4"]["definitionExpression"], 
                             "Layer with layerDefinition but no definitionExpression should have None")
            
            self.assertEqual(result["https://services.arcgis.com/layer5"]["definitionExpression"], "status = 'PENDING'", 
                            "Layer with layerDefinition and definitionExpression should have correct value")
            
            self.assertEqual(result["https://services.arcgis.com/layer6"]["definitionExpression"], "status = 'CURRENT'", 
                            "Layer with both definitionExpression locations should have layerDefinition value")
            
            self.assertIsNone(result["https://services.arcgis.com/layer7"]["definitionExpression"], 
                             "Nested layer with no definitionExpression should have None")
            
            self.assertEqual(result["https://services.arcgis.com/layer8"]["definitionExpression"], "status = 'NESTED'", 
                            "Nested layer with layerDefinition should have correct value")
    
    @patch('patch_webmap_filters.gis')
    @patch('patch_webmap_filters.FeatureLayer')
    @patch('patch_webmap_filters.get_webmap_item')
    def test_update_webmap_definition_by_field(self, mock_get_webmap_item, mock_feature_layer_class, mock_gis):
        """Test update_webmap_definition_by_field function with different layer configurations"""
        # Configure mocks
        mock_gis.return_value = self.mock_gis
        mock_get_webmap_item.return_value = self.mock_webmap_item
        
        # Create mock feature layers for each URL
        mock_feature_layers = {}
        for layer in self.test_layers:
            if "url" in layer:
                url = layer["url"]
                mock_feature_layers[url] = MockFeatureLayer(url)
            elif "layers" in layer:
                for nested_layer in layer["layers"]:
                    if "url" in nested_layer:
                        url = nested_layer["url"]
                        mock_feature_layers[url] = MockFeatureLayer(url)
        
        # Configure mock_feature_layer_class to return appropriate mock feature layer
        mock_feature_layer_class.side_effect = lambda url, gis: mock_feature_layers.get(url)
        
        # Mock layer_contains_field to always return True for testing
        with patch('patch_webmap_filters.layer_contains_field', return_value=True):
            # Set DEBUG_MODE to True to avoid actual server updates
            with patch('patch_webmap_filters.DEBUG_MODE', True):
                # Call the function
                result = update_webmap_definition_by_field(
                    self.webmap_item_id, 
                    self.target_field, 
                    self.new_filter
                )
                
                # Verify results
                self.assertEqual(len(result), 8, "Should update all 8 feature layers")
                
                # Check that all layers were updated correctly
                for layer in self.test_layers:
                    if "url" in layer:
                        url = layer["url"]
                        # Check layerDefinition was created if it didn't exist
                        self.assertIn("layerDefinition", layer, 
                                     f"Layer {layer['title']} should have layerDefinition")
                        
                        # Check definitionExpression was set in layerDefinition
                        self.assertEqual(layer["layerDefinition"]["definitionExpression"], self.new_filter,
                                        f"Layer {layer['title']} should have definitionExpression in layerDefinition")
                    elif "layers" in layer:
                        for nested_layer in layer["layers"]:
                            if "url" in nested_layer:
                                # Check layerDefinition was created if it didn't exist
                                self.assertIn("layerDefinition", nested_layer, 
                                             f"Nested layer {nested_layer['title']} should have layerDefinition")
                                
                                # Check definitionExpression was set in layerDefinition
                                self.assertEqual(nested_layer["layerDefinition"]["definitionExpression"], self.new_filter,
                                                f"Nested layer {nested_layer['title']} should have definitionExpression in layerDefinition")
    
    def test_verify_webmap_changes(self):
        """Test verify_webmap_changes function with different scenarios"""
        # Test case 1: Changes successful
        before_state = {
            "https://services.arcgis.com/layer1": {
                "title": "Layer 1",
                "definitionExpression": None
            },
            "https://services.arcgis.com/layer2": {
                "title": "Layer 2",
                "definitionExpression": "old_filter"
            }
        }
        
        after_state = {
            "https://services.arcgis.com/layer1": {
                "title": "Layer 1",
                "definitionExpression": "new_filter"
            },
            "https://services.arcgis.com/layer2": {
                "title": "Layer 2",
                "definitionExpression": "old_filter"  # Unchanged
            }
        }
        
        result = verify_webmap_changes(before_state, after_state, "new_filter")
        
        self.assertTrue(result, "Should report success when at least one layer is updated correctly")
        
        # Test case 2: No changes successful
        before_state = {
            "https://services.arcgis.com/layer1": {
                "title": "Layer 1",
                "definitionExpression": None
            },
            "https://services.arcgis.com/layer2": {
                "title": "Layer 2",
                "definitionExpression": "old_filter"
            }
        }
        
        after_state = {
            "https://services.arcgis.com/layer1": {
                "title": "Layer 1",
                "definitionExpression": "wrong_filter"  # Changed but incorrect
            },
            "https://services.arcgis.com/layer2": {
                "title": "Layer 2",
                "definitionExpression": "old_filter"  # Unchanged
            }
        }
        
        result = verify_webmap_changes(before_state, after_state, "new_filter")
        
        self.assertFalse(result, "Should report failure when no layers are updated correctly")
        
        # Test case 3: Empty before state
        before_state = {}
        after_state = {
            "https://services.arcgis.com/layer1": {
                "title": "Layer 1",
                "definitionExpression": "new_filter"
            }
        }
        
        result = verify_webmap_changes(before_state, after_state, "new_filter")
        
        self.assertFalse(result, "Should report failure with empty before state")

if __name__ == "__main__":
    unittest.main()
