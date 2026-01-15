"""
Core clipping operations for processing Feature Layers with template geometries.
Provides batch processing capabilities with progress tracking and error handling.
"""

# Note: UI functions (show_clip_results, etc.) should be moved to frontend
import logging
from typing import List, Optional, Dict, Any, Tuple
from arcgis.gis import GIS, Item
from arcgis.features import FeatureLayer, FeatureSet
from arcgis.geometry import Geometry
from arcgis.geometry.functions import intersect

from backend.utils.logging import get_logger
from backend.core.clip.geometry import prepare_template_geometry, validate_geometry, geometry_summary

# Configure logging
logger = get_logger("clip_operations")


class ClipResult:
    """Container for clipping operation results."""
    
    def __init__(self, source_item: Item, success: bool, message: str, output_item: Item = None):
        self.source_item = source_item
        self.success = success
        self.message = message
        self.output_item = output_item
        self.feature_count = 0
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            'source_title': self.source_item.title,
            'source_id': self.source_item.id,
            'success': self.success,
            'message': self.message,
            'output_item_id': self.output_item.id if self.output_item else None,
            'output_title': self.output_item.title if self.output_item else None,
            'feature_count': self.feature_count
        }


def clip_feature_layer(
    template_geometry: Geometry,
    target_item: Item,
    output_crs: Dict[str, Any],
    gis: GIS,
    debug_mode: bool = True
) -> ClipResult:
    """
    Clip a single feature layer using the template geometry.
    
    Args:
        template_geometry: The geometry to use for clipping
        target_item: The Feature Layer item to clip
        output_crs: Target coordinate system for output
        gis: The authenticated GIS object
        debug_mode: Whether to simulate the operation
        
    Returns:
        ClipResult object with operation details
    """
    logger.info(f"Starting clip operation for layer: {target_item.title}")
    
    try:
        # Validate template geometry
        is_valid, validation_msg = validate_geometry(template_geometry)
        if not is_valid:
            return ClipResult(
                target_item, 
                False, 
                f"Invalid template geometry: {validation_msg}"
            )
        
        # Get the feature layer
        feature_layer = FeatureLayer.fromitem(target_item)
        
        # Validate feature layer access
        if not feature_layer or not hasattr(feature_layer, 'properties'):
            return ClipResult(
                target_item,
                False,
                "Cannot access feature layer properties"
            )
        
        # Check layer capabilities
        capabilities = feature_layer.properties.get('capabilities', '')
        if 'Query' not in capabilities:
            return ClipResult(
                target_item,
                False,
                "Layer does not support querying"
            )
        
        # Get layer's spatial reference
        layer_extent = feature_layer.properties.get('extent', {})
        layer_sr = layer_extent.get('spatialReference', {})
        
        logger.debug(f"Layer spatial reference: {layer_sr}")
        logger.debug(f"Output spatial reference: {output_crs}")
        
        # Query all features from the layer
        logger.info("Querying features from target layer")
        feature_set = feature_layer.query(
            where='1=1',
            return_geometry=True,
            out_sr=layer_sr.get('wkid', 4326)
        )
        
        if not feature_set.features:
            return ClipResult(
                target_item,
                False,
                "No features found in layer"
            )
        
        logger.info(f"Found {len(feature_set.features)} features to process")
        
        # Perform intersection/clipping
        clipped_features = []
        
        for feature in feature_set.features:
            if feature.geometry:
                try:
                    # Use ArcGIS geometry intersection
                    intersected_geom = intersect(
                        geometries=[feature.geometry],
                        intersector=template_geometry,
                        gis=gis
                    )
                    
                    if intersected_geom and len(intersected_geom) > 0 and intersected_geom[0]:
                        # Create new feature with clipped geometry
                        clipped_feature = feature
                        clipped_feature.geometry = intersected_geom[0]
                        clipped_features.append(clipped_feature)
                        
                except Exception as e:
                    logger.warning(f"Failed to clip feature: {str(e)}")
                    continue
        
        if not clipped_features:
            return ClipResult(
                target_item,
                False,
                "No features intersect with template geometry"
            )
        
        logger.info(f"Successfully clipped {len(clipped_features)} features")
        
        # Create output feature set
        clipped_feature_set = FeatureSet(
            features=clipped_features,
            geometry_type=feature_set.geometry_type,
            spatial_reference=output_crs
        )
        
        # Generate output name
        output_title = f"{target_item.title}_clipped"
        
        if debug_mode:
            # In debug mode, don't actually create the layer
            result = ClipResult(
                target_item,
                True,
                f"DEBUG: Would create layer '{output_title}' with {len(clipped_features)} features"
            )
            result.feature_count = len(clipped_features)
            return result
        
        # Create new feature layer in AGOL
        logger.info(f"Creating output feature layer: {output_title}")
        
        # Publish the feature set as a new layer
        output_item = gis.content.import_data(
            clipped_feature_set,
            title=output_title,
            tags=target_item.tags + ['clipped'],
            description=f"Clipped version of {target_item.title}"
        )
        
        if output_item:
            logger.info(f"Successfully created output layer: {output_item.id}")
            result = ClipResult(
                target_item,
                True,
                f"Successfully created clipped layer with {len(clipped_features)} features",
                output_item
            )
            result.feature_count = len(clipped_features)
            return result
        else:
            return ClipResult(
                target_item,
                False,
                "Failed to create output feature layer"
            )
            
    except Exception as e:
        error_msg = f"Error clipping layer: {str(e)}"
        logger.error(f"Clip operation failed for {target_item.title}: {error_msg}")
        return ClipResult(target_item, False, error_msg)


def batch_clip_layers(
    template_config: Dict[str, Any],
    target_items: List[Item],
    output_config: Dict[str, Any],
    gis: GIS,
    debug_mode: bool = True
) -> List[ClipResult]:
    """
    Process multiple layers with clipping operations.
    
    Args:
        template_config: Configuration for template geometry
        target_items: List of Feature Layer items to clip
        output_config: Configuration for output layers
        gis: The authenticated GIS object
        debug_mode: Whether to simulate operations
        
    Returns:
        List of ClipResult objects
    """
    logger.info(f"Starting batch clip operation for {len(target_items)} layers")
    
    if len(target_items) > 10:
        logger.warning(f"Too many layers requested: {len(target_items)}. Limiting to 10.")
        target_items = target_items[:10]
    
    results = []
    
    # Prepare template geometry
    template_layer = template_config.get('feature_layer')
    where_clause = template_config.get('where_clause')
    buffer_distance = template_config.get('buffer_distance', 0)
    buffer_unit = template_config.get('buffer_unit', 'meters')
    output_crs = output_config.get('spatial_reference', {})
    
    # Show initial status
    status_container, progress_bar = show_operation_status(
        "Clip Operation",
        total_items=len(target_items) + 1,  # +1 for template preparation
        current_item=1,
        current_item_name="Preparing template geometry"
    )
    
    try:
        # Prepare template geometry
        template_geometry = prepare_template_geometry(
            feature_layer=template_layer,
            where_clause=where_clause,
            buffer_distance=buffer_distance,
            buffer_unit=buffer_unit,
            target_spatial_reference=output_crs,
            gis=gis
        )
        
        if not template_geometry:
            complete_operation_status(
                status_container,
                progress_bar,
                "Clip Operation",
                False,
                "Failed to prepare template geometry"
            )
            return results
        
        logger.info("Template geometry prepared successfully")
        
        # Process each target layer
        for i, target_item in enumerate(target_items, 1):
            update_operation_status(
                status_container,
                progress_bar,
                "Clip Operation",
                total_items=len(target_items) + 1,
                current_item=i + 1,
                current_item_name=target_item.title
            )
            
            # Perform clipping operation
            result = clip_feature_layer(
                template_geometry=template_geometry,
                target_item=target_item,
                output_crs=output_crs,
                gis=gis,
                debug_mode=debug_mode
            )
            
            results.append(result)
            
            # Log result
            if result.success:
                logger.info(f"✓ {target_item.title}: {result.message}")
            else:
                logger.warning(f"✗ {target_item.title}: {result.message}")
        
        # Complete operation
        successful_count = sum(1 for r in results if r.success)
        failed_count = len(results) - successful_count
        
        completion_message = f"Completed: {successful_count} successful, {failed_count} failed"
        
        complete_operation_status(
            status_container,
            progress_bar,
            "Clip Operation",
            successful_count > 0,
            completion_message,
            {
                "Total Layers": len(target_items),
                "Successful": successful_count,
                "Failed": failed_count,
                "Debug Mode": debug_mode
            }
        )
        
    except Exception as e:
        logger.error(f"Batch clip operation failed: {str(e)}")
        complete_operation_status(
            status_container,
            progress_bar,
            "Clip Operation",
            False,
            f"Operation failed: {str(e)}"
        )
    
    logger.info(f"Batch clip operation completed with {len(results)} results")
    return results


def show_clip_results(results: List[ClipResult]) -> None:
    """
    Display the results of clipping operations in a user-friendly format.
    
    Args:
        results: List of ClipResult objects to display
    """
    if not results:
        st.warning("No results to display")
        return
    
    st.subheader("Clipping Results")
    
    # Summary metrics
    successful_count = sum(1 for r in results if r.success)
    failed_count = len(results) - successful_count
    total_features = sum(r.feature_count for r in results if r.success)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Successful", successful_count, delta=None)
    with col2:
        st.metric("Failed", failed_count, delta=None)
    with col3:
        st.metric("Total Features", total_features, delta=None)
    
    # Detailed results
    if successful_count > 0:
        st.subheader("Successful Operations")
        for result in results:
            if result.success:
                with st.expander(f"✓ {result.source_item.title}", expanded=False):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**Source Layer:** {result.source_item.title}")
                        st.write(f"**Source ID:** {result.source_item.id}")
                        st.write(f"**Features Clipped:** {result.feature_count}")
                    with col2:
                        if result.output_item:
                            st.write(f"**Output Layer:** {result.output_item.title}")
                            st.write(f"**Output ID:** {result.output_item.id}")
                            st.write(f"**Status:** {result.message}")
                        else:
                            st.write(f"**Status:** {result.message}")
    
    if failed_count > 0:
        st.subheader("Failed Operations")
        for result in results:
            if not result.success:
                with st.expander(f"✗ {result.source_item.title}", expanded=False):
                    st.write(f"**Source Layer:** {result.source_item.title}")
                    st.write(f"**Source ID:** {result.source_item.id}")
                    st.error(f"**Error:** {result.message}")
                    
                    # Show troubleshooting suggestions
                    st.info("""
                    **Possible solutions:**
                    - Check if the layer is accessible and has the required permissions
                    - Verify that the layer contains features that intersect with the template geometry
                    - Ensure the layer supports querying operations
                    - Try running in debug mode to see more details
                    """)


def validate_clip_inputs(
    template_layer: FeatureLayer,
    target_items: List[Item],
    output_crs: Dict[str, Any]
) -> Tuple[bool, List[str]]:
    """
    Validate inputs for clipping operations.
    
    Args:
        template_layer: The template feature layer
        target_items: List of target items to clip
        output_crs: Output coordinate system configuration
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    errors = []
    
    # Validate template layer
    if not template_layer:
        errors.append("Template layer is required")
    else:
        try:
            if not hasattr(template_layer, 'properties') or not template_layer.properties:
                errors.append("Cannot access template layer properties")
        except Exception as e:
            errors.append(f"Error accessing template layer: {str(e)}")
    
    # Validate target items
    if not target_items:
        errors.append("At least one target layer must be selected")
    elif len(target_items) > 10:
        errors.append("Maximum 10 layers can be processed at once")
    else:
        for item in target_items:
            if item.type != "Feature Layer":
                errors.append(f"Item '{item.title}' is not a Feature Layer")
    
    # Validate output coordinate system
    if not output_crs or not output_crs.get('wkid'):
        errors.append("Output coordinate system is required")
    
    return len(errors) == 0, errors


def create_clip_help_section() -> None:
    """Create a comprehensive help section for the clipping tool."""
    with st.expander("Clip Operation Help", expanded=False):
        st.markdown("""
        ### How Clipping Works
        
        **Template Geometry:**
        - Select a Feature Layer to use as the clipping template
        - Optionally filter features with a WHERE clause
        - Apply a buffer distance to expand the clipping area
        
        **Target Layers:**
        - Search for layers using comma-delimited tags
        - Select up to 10 layers to clip
        - Only vector Feature Layers are supported
        
        **Output:**
        - Creates new Feature Layers with "_clipped" suffix
        - Saves to your root AGOL folder
        - Preserves original attributes and styling where possible
        
        **Process:**
        1. Template geometry is prepared (filtered, buffered, projected)
        2. Each target layer is queried for all features
        3. Features are clipped using geometric intersection
        4. New Feature Layers are created with clipped results
        
        **Error Handling:**
        - Layers that fail are skipped with detailed error messages
        - Operation continues with remaining layers
        - Debug mode allows testing without creating actual outputs
        
        **Tips:**
        - Use debug mode first to test your configuration
        - Ensure template and target layers have overlapping areas
        - Check layer permissions if operations fail
        - Buffer distance can help capture edge features
        """)


def show_template_geometry_preview(
    template_layer: FeatureLayer,
    where_clause: str = None,
    buffer_distance: float = 0,
    buffer_unit: str = "meters"
) -> None:
    """
    Show a preview of the template geometry configuration.
    
    Args:
        template_layer: The template feature layer
        where_clause: Optional WHERE clause
        buffer_distance: Buffer distance
        buffer_unit: Buffer unit
    """
    if not template_layer:
        return
    
    with st.expander("Template Geometry Preview", expanded=False):
        try:
            # Get basic layer info
            layer_props = template_layer.properties
            
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**Layer Type:** {layer_props.get('geometryType', 'Unknown')}")
                st.write(f"**Feature Count:** {layer_props.get('count', 'Unknown')}")
                
            with col2:
                extent = layer_props.get('extent', {})
                if extent:
                    sr = extent.get('spatialReference', {})
                    st.write(f"**Coordinate System:** {sr.get('wkid', 'Unknown')}")
                
            # Show WHERE clause if specified
            if where_clause and where_clause.strip() != '1=1':
                st.write(f"**Filter:** {where_clause}")
            else:
                st.write("**Filter:** All features")
            
            # Show buffer if specified
            if buffer_distance > 0:
                st.write(f"**Buffer:** {buffer_distance} {buffer_unit}")
            else:
                st.write("**Buffer:** None")
                
            # Try to get a feature count with the WHERE clause
            if where_clause:
                try:
                    filtered_count = template_layer.query(
                        where=where_clause,
                        return_count_only=True
                    )
                    st.write(f"**Filtered Features:** {filtered_count}")
                except Exception as e:
                    st.warning(f"Could not count filtered features: {str(e)}")
                    
        except Exception as e:
            st.error(f"Error previewing template geometry: {str(e)}")
