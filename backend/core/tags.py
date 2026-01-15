"""
Tag management utilities for discovering and filtering ArcGIS items by tags.
Core backend logic with no Streamlit dependencies.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from arcgis.gis import GIS, Item
from arcgis.features import FeatureLayer

from backend.utils.logging import get_logger

logger = get_logger("tags")


def parse_tags(tag_string: str) -> List[str]:
    """
    Parse comma-delimited tag string into a list of individual tags.
    
    Args:
        tag_string: Comma-delimited string of tags
        
    Returns:
        List of cleaned tag strings
    """
    if not tag_string:
        return []
    
    # Split by comma and clean up whitespace
    tags = [tag.strip() for tag in tag_string.split(",") if tag.strip()]
    logger.debug(f"Parsed tags: {tags}")
    return tags


def search_layers_by_tags(
    gis: GIS, 
    tags: List[str], 
    search_org_only: bool = True, 
    max_results: int = 50
) -> List[Item]:
    """
    Search for Feature Layers containing any of the specified tags.
    
    Args:
        gis: The authenticated GIS object
        tags: List of tags to search for
        search_org_only: Whether to search within organization only
        max_results: Maximum number of results to return
        
    Returns:
        List of Feature Layer items that contain any of the specified tags
    """
    if not tags:
        logger.warning("No tags provided for search")
        return []
    
    matching_items = []
    
    try:
        # Create search query for tags
        # Use OR logic to find items with any of the specified tags
        tag_queries = [f'tags:"{tag}"' for tag in tags]
        tag_query = " OR ".join(tag_queries)
        
        # Combine with item type filter
        full_query = f"({tag_query}) AND type:\"Feature Layer\""
        
        logger.info(f"Searching with query: {full_query}")
        logger.info(f"Search scope: {'Organization only' if search_org_only else 'Public AGOL'}")
        
        # Perform search
        search_results = gis.content.search(
            query=full_query,
            item_type="Feature Layer",
            max_items=max_results,
            outside_org=not search_org_only
        )
        
        # Filter results to ensure they actually contain the tags
        for item in search_results:
            if item.tags and any(tag.lower() in [t.lower() for t in item.tags] for tag in tags):
                matching_items.append(item)
                logger.debug(f"Found matching layer: {item.title} (tags: {item.tags})")
        
        logger.info(f"Found {len(matching_items)} Feature Layers with matching tags")
        
    except Exception as e:
        logger.error(f"Error searching for layers by tags: {str(e)}")
        raise
    
    return matching_items


def extract_layer_coordinate_systems(items: List[Item]) -> List[Dict[str, Any]]:
    """
    Extract unique coordinate systems from a list of Feature Layer items.
    
    Args:
        items: List of Feature Layer items
        
    Returns:
        List of coordinate system dictionaries with 'name', 'wkid', and 'item_title'
    """
    coordinate_systems = []
    seen_wkids = set()
    
    for item in items:
        try:
            # Get the feature layer
            feature_layer = FeatureLayer.fromitem(item)
            
            # Extract spatial reference information
            if hasattr(feature_layer, 'properties') and feature_layer.properties:
                extent = feature_layer.properties.get('extent')
                if extent and 'spatialReference' in extent:
                    spatial_ref = extent['spatialReference']
                    wkid = spatial_ref.get('wkid')
                    
                    if wkid and wkid not in seen_wkids:
                        # Try to get a readable name for the coordinate system
                        crs_name = spatial_ref.get('latestWkid', wkid)
                        
                        # Common coordinate system names
                        common_names = {
                            4326: "WGS 84 (Geographic)",
                            3857: "Web Mercator",
                            102100: "Web Mercator Auxiliary Sphere",
                            4269: "NAD 83 (Geographic)",
                            3826: "TWD97 / TM2 zone 121",
                            2154: "RGF93 / Lambert-93"
                        }
                        
                        display_name = common_names.get(wkid, f"EPSG:{wkid}")
                        
                        coordinate_systems.append({
                            'name': display_name,
                            'wkid': wkid,
                            'item_title': item.title,
                            'spatial_reference': spatial_ref
                        })
                        
                        seen_wkids.add(wkid)
                        logger.debug(f"Found CRS {display_name} (WKID: {wkid}) from layer: {item.title}")
        
        except Exception as e:
            logger.warning(f"Could not extract coordinate system from layer {item.title}: {str(e)}")
            continue
    
    logger.info(f"Extracted {len(coordinate_systems)} unique coordinate systems")
    return coordinate_systems


def validate_feature_layer_access(gis: GIS, item: Item) -> Tuple[bool, str]:
    """
    Validate that a Feature Layer item is accessible and can be used for clipping.
    
    Args:
        gis: The authenticated GIS object
        item: The Feature Layer item to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check if item exists and is accessible
        if not item:
            return False, "Item not found"
        
        # Check if it's actually a Feature Layer
        if item.type != "Feature Layer":
            return False, f"Item is not a Feature Layer (type: {item.type})"
        
        # Try to create a FeatureLayer object
        feature_layer = FeatureLayer.fromitem(item)
        
        # Check if we can access basic properties
        if not hasattr(feature_layer, 'properties') or not feature_layer.properties:
            return False, "Cannot access layer properties"
        
        # Check if layer has geometry
        geometry_type = feature_layer.properties.get('geometryType')
        if not geometry_type:
            return False, "Layer does not have geometry information"
        
        # Check if layer is queryable
        capabilities = feature_layer.properties.get('capabilities', '')
        if 'Query' not in capabilities:
            return False, "Layer does not support querying"
        
        logger.debug(f"Layer {item.title} validated successfully")
        return True, "Valid"
        
    except Exception as e:
        error_msg = f"Error validating layer: {str(e)}"
        logger.warning(f"Validation failed for layer {item.title}: {error_msg}")
        return False, error_msg
