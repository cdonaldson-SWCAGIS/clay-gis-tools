"""
Geometry utilities for spatial operations including buffering and coordinate transformations.
Provides functionality for processing template geometries and preparing them for clipping operations.
"""

import logging
from typing import Optional, Dict, Any, Union, Tuple
from arcgis.gis import GIS
from arcgis.features import FeatureLayer
from arcgis.geometry import Geometry, Point, Polygon, Polyline
from arcgis.geometry.functions import buffer, project

# Configure logging
logger = logging.getLogger("geometry_utils")


class BufferUnits:
    """Constants for buffer distance units."""
    METERS = "meters"
    FEET = "feet"
    KILOMETERS = "kilometers"
    MILES = "miles"
    
    # Conversion factors to meters
    CONVERSIONS = {
        METERS: 1.0,
        FEET: 0.3048,
        KILOMETERS: 1000.0,
        MILES: 1609.344
    }
    
    @classmethod
    def get_all_units(cls) -> list:
        """Get list of all available units."""
        return [cls.METERS, cls.FEET, cls.KILOMETERS, cls.MILES]
    
    @classmethod
    def convert_to_meters(cls, distance: float, unit: str) -> float:
        """Convert distance to meters."""
        if unit not in cls.CONVERSIONS:
            raise ValueError(f"Unknown unit: {unit}")
        return distance * cls.CONVERSIONS[unit]


def get_template_geometry(
    feature_layer: FeatureLayer,
    where_clause: str = None,
    gis: GIS = None
) -> Optional[Geometry]:
    """
    Extract geometry from a feature layer to use as a template for clipping.
    
    Args:
        feature_layer: The FeatureLayer to extract geometry from
        where_clause: Optional SQL where clause to filter features
        gis: The authenticated GIS object
        
    Returns:
        Combined geometry from all matching features, or None if no features found
    """
    if not feature_layer:
        logger.error("No feature layer provided")
        return None
    
    try:
        # Build query parameters
        query_params = {
            'where': where_clause or '1=1',
            'return_geometry': True,
            'out_sr': feature_layer.properties.extent.get('spatialReference', {}).get('wkid', 4326)
        }
        
        logger.info(f"Querying template layer with where clause: {query_params['where']}")
        
        # Query features
        feature_set = feature_layer.query(**query_params)
        
        if not feature_set.features:
            logger.warning("No features found matching the where clause")
            return None
        
        logger.info(f"Found {len(feature_set.features)} features for template geometry")
        
        # Extract geometries
        geometries = []
        for feature in feature_set.features:
            if feature.geometry:
                geometries.append(feature.geometry)
        
        if not geometries:
            logger.warning("No valid geometries found in features")
            return None
        
        # If single geometry, return it directly
        if len(geometries) == 1:
            return geometries[0]
        
        # For multiple geometries, union them
        logger.info(f"Combining {len(geometries)} geometries into single template")
        combined_geometry = union_geometries(geometries)
        
        return combined_geometry
        
    except Exception as e:
        logger.error(f"Error extracting template geometry: {str(e)}")
        return None


def union_geometries(geometries: list) -> Optional[Geometry]:
    """
    Union multiple geometries into a single geometry.
    
    Args:
        geometries: List of Geometry objects to union
        
    Returns:
        Combined geometry or None if union fails
    """
    if not geometries:
        return None
    
    if len(geometries) == 1:
        return geometries[0]
    
    try:
        # Start with first geometry
        result = geometries[0]
        
        # Union with each subsequent geometry
        for geom in geometries[1:]:
            if result and geom:
                # Use the union method if available
                if hasattr(result, 'union'):
                    result = result.union(geom)
                else:
                    # Fallback to geometry service union
                    from arcgis.geometry.functions import union
                    result = union([result, geom])
        
        logger.debug(f"Successfully unioned {len(geometries)} geometries")
        return result
        
    except Exception as e:
        logger.error(f"Error unioning geometries: {str(e)}")
        return None


def apply_buffer(
    geometry: Geometry,
    buffer_distance: float,
    buffer_unit: str = BufferUnits.METERS,
    gis: GIS = None
) -> Optional[Geometry]:
    """
    Apply a buffer to a geometry.
    
    Args:
        geometry: The geometry to buffer
        buffer_distance: Buffer distance
        buffer_unit: Unit for buffer distance
        gis: The authenticated GIS object
        
    Returns:
        Buffered geometry or original geometry if buffer_distance is 0
    """
    if not geometry:
        logger.error("No geometry provided for buffering")
        return None
    
    if buffer_distance <= 0:
        logger.debug("Buffer distance is 0 or negative, returning original geometry")
        return geometry
    
    try:
        # Convert buffer distance to meters if needed
        if buffer_unit != BufferUnits.METERS:
            buffer_distance_meters = BufferUnits.convert_to_meters(buffer_distance, buffer_unit)
            logger.debug(f"Converted buffer distance: {buffer_distance} {buffer_unit} = {buffer_distance_meters} meters")
        else:
            buffer_distance_meters = buffer_distance
        
        logger.info(f"Applying buffer of {buffer_distance_meters} meters to geometry")
        
        # Apply buffer using ArcGIS geometry functions
        buffered_geometry = buffer(
            geometries=[geometry],
            distances=[buffer_distance_meters],
            unit='meters',
            gis=gis
        )
        
        if buffered_geometry and len(buffered_geometry) > 0:
            logger.debug("Buffer operation successful")
            return buffered_geometry[0]
        else:
            logger.warning("Buffer operation returned no results")
            return geometry
            
    except Exception as e:
        logger.error(f"Error applying buffer: {str(e)}")
        logger.warning("Returning original geometry without buffer")
        return geometry


def transform_geometry(
    geometry: Geometry,
    target_spatial_reference: Dict[str, Any],
    gis: GIS = None
) -> Optional[Geometry]:
    """
    Transform geometry to a target spatial reference system.
    
    Args:
        geometry: The geometry to transform
        target_spatial_reference: Target spatial reference dictionary
        gis: The authenticated GIS object
        
    Returns:
        Transformed geometry or original geometry if transformation fails
    """
    if not geometry:
        logger.error("No geometry provided for transformation")
        return None
    
    if not target_spatial_reference:
        logger.warning("No target spatial reference provided, returning original geometry")
        return geometry
    
    try:
        # Get current spatial reference
        current_sr = geometry.spatial_reference
        target_wkid = target_spatial_reference.get('wkid')
        
        # Check if transformation is needed
        if current_sr and current_sr.get('wkid') == target_wkid:
            logger.debug("Geometry already in target coordinate system")
            return geometry
        
        logger.info(f"Transforming geometry from {current_sr} to {target_spatial_reference}")
        
        # Project geometry to target spatial reference
        transformed_geometry = project(
            geometries=[geometry],
            out_sr=target_spatial_reference,
            gis=gis
        )
        
        if transformed_geometry and len(transformed_geometry) > 0:
            logger.debug("Geometry transformation successful")
            return transformed_geometry[0]
        else:
            logger.warning("Geometry transformation returned no results")
            return geometry
            
    except Exception as e:
        logger.error(f"Error transforming geometry: {str(e)}")
        logger.warning("Returning original geometry without transformation")
        return geometry


def prepare_template_geometry(
    feature_layer: FeatureLayer,
    where_clause: str = None,
    buffer_distance: float = 0,
    buffer_unit: str = BufferUnits.METERS,
    target_spatial_reference: Dict[str, Any] = None,
    gis: GIS = None
) -> Optional[Geometry]:
    """
    Complete workflow to prepare a template geometry for clipping operations.
    
    Args:
        feature_layer: The FeatureLayer to extract geometry from
        where_clause: Optional SQL where clause to filter features
        buffer_distance: Buffer distance to apply
        buffer_unit: Unit for buffer distance
        target_spatial_reference: Target spatial reference for output
        gis: The authenticated GIS object
        
    Returns:
        Prepared geometry ready for clipping operations
    """
    logger.info("Starting template geometry preparation workflow")
    
    # Step 1: Extract geometry from feature layer
    template_geometry = get_template_geometry(feature_layer, where_clause, gis)
    if not template_geometry:
        logger.error("Failed to extract template geometry")
        return None
    
    # Step 2: Apply buffer if specified
    if buffer_distance > 0:
        template_geometry = apply_buffer(
            template_geometry, 
            buffer_distance, 
            buffer_unit, 
            gis
        )
        if not template_geometry:
            logger.error("Failed to apply buffer to template geometry")
            return None
    
    # Step 3: Transform to target coordinate system if specified
    if target_spatial_reference:
        template_geometry = transform_geometry(
            template_geometry,
            target_spatial_reference,
            gis
        )
        if not template_geometry:
            logger.error("Failed to transform template geometry")
            return None
    
    logger.info("Template geometry preparation completed successfully")
    return template_geometry


def validate_geometry(geometry: Geometry) -> Tuple[bool, str]:
    """
    Validate that a geometry is suitable for clipping operations.
    
    Args:
        geometry: The geometry to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not geometry:
        return False, "Geometry is None"
    
    try:
        # Check if geometry has a type
        if not hasattr(geometry, 'type') or not geometry.type:
            return False, "Geometry has no type"
        
        # Check for valid geometry types for clipping
        valid_types = ['polygon', 'polyline', 'point', 'multipoint']
        if geometry.type.lower() not in valid_types:
            return False, f"Unsupported geometry type: {geometry.type}"
        
        # Check if geometry has coordinates
        if not hasattr(geometry, 'coordinates') and not hasattr(geometry, 'rings'):
            return False, "Geometry has no coordinate data"
        
        # For polygons, check if they have rings
        if geometry.type.lower() == 'polygon':
            if not hasattr(geometry, 'rings') or not geometry.rings:
                return False, "Polygon geometry has no rings"
        
        # Check spatial reference
        if hasattr(geometry, 'spatial_reference'):
            sr = geometry.spatial_reference
            if sr and not sr.get('wkid') and not sr.get('wkt'):
                return False, "Geometry has invalid spatial reference"
        
        logger.debug(f"Geometry validation successful: {geometry.type}")
        return True, "Valid"
        
    except Exception as e:
        error_msg = f"Error validating geometry: {str(e)}"
        logger.warning(error_msg)
        return False, error_msg


def get_geometry_extent(geometry: Geometry) -> Optional[Dict[str, float]]:
    """
    Get the extent (bounding box) of a geometry.
    
    Args:
        geometry: The geometry to get extent for
        
    Returns:
        Dictionary with xmin, ymin, xmax, ymax or None if failed
    """
    if not geometry:
        return None
    
    try:
        if hasattr(geometry, 'extent'):
            extent = geometry.extent
            return {
                'xmin': extent[0],
                'ymin': extent[1],
                'xmax': extent[2],
                'ymax': extent[3]
            }
        elif hasattr(geometry, 'coordinates'):
            # Calculate extent from coordinates
            coords = geometry.coordinates
            if coords:
                # Flatten coordinates if nested
                flat_coords = []
                def flatten(coord_list):
                    for item in coord_list:
                        if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[0], (int, float)):
                            flat_coords.append(item)
                        elif isinstance(item, (list, tuple)):
                            flatten(item)
                
                flatten(coords)
                
                if flat_coords:
                    x_coords = [coord[0] for coord in flat_coords]
                    y_coords = [coord[1] for coord in flat_coords]
                    
                    return {
                        'xmin': min(x_coords),
                        'ymin': min(y_coords),
                        'xmax': max(x_coords),
                        'ymax': max(y_coords)
                    }
        
        logger.warning("Could not determine geometry extent")
        return None
        
    except Exception as e:
        logger.error(f"Error getting geometry extent: {str(e)}")
        return None


def geometry_summary(geometry: Geometry) -> Dict[str, Any]:
    """
    Get a summary of geometry properties for display purposes.
    
    Args:
        geometry: The geometry to summarize
        
    Returns:
        Dictionary with geometry summary information
    """
    if not geometry:
        return {"error": "No geometry provided"}
    
    try:
        summary = {
            "type": getattr(geometry, 'type', 'Unknown'),
            "spatial_reference": getattr(geometry, 'spatial_reference', None),
            "is_valid": validate_geometry(geometry)[0]
        }
        
        # Add extent information
        extent = get_geometry_extent(geometry)
        if extent:
            summary["extent"] = extent
        
        # Add coordinate count for different geometry types
        if hasattr(geometry, 'coordinates'):
            coords = geometry.coordinates
            if coords:
                summary["coordinate_count"] = len(str(coords).split(','))
        elif hasattr(geometry, 'rings'):
            rings = geometry.rings
            if rings:
                total_points = sum(len(ring) for ring in rings)
                summary["total_points"] = total_points
                summary["ring_count"] = len(rings)
        
        return summary
        
    except Exception as e:
        logger.error(f"Error creating geometry summary: {str(e)}")
        return {"error": str(e)}
