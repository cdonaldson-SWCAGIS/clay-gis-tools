"""
Bulk Collections Creation Tool

Allows users to create photo collections in bulk by:
1. Selecting a web map
2. Choosing layers with attachments enabled
3. Selecting a match field for each layer
4. Querying features and grouping by common match values
5. Generating and validating the collection payload
"""

import streamlit as st
import pandas as pd
import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

# Import utility modules
import sys
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from frontend.components.item_selector import ItemSelector
from frontend.components.common_operations import (
    ensure_authentication, get_gis_object, show_tool_header
)
from backend.core.webmap.utils import (
    get_webmap_layer_details_with_attachments,
    query_features_by_field,
    get_layer_attachments,
    get_feature_layer
)

# Import AgGrid components
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode

# Configure logging
logger = logging.getLogger("bulk_collections")


def load_js_file(js_file_path: str) -> JsCode:
    """Load a JavaScript file and return it as a JsCode object for use with AgGrid."""
    project_root = Path(__file__).parent.parent.parent
    full_path = project_root / js_file_path
    
    if not full_path.exists():
        logger.error(f"JavaScript file not found: {full_path}")
        raise FileNotFoundError(f"JavaScript file not found: {full_path}")
    
    with open(full_path, 'r', encoding='utf-8') as f:
        js_content = f.read()
    
    return JsCode(js_content)


def show():
    """Display the Bulk Collections interface"""
    # Check authentication first
    if not ensure_authentication():
        return
    
    # Show tool header
    show_tool_header(
        "Bulk Create Collections",
        "Create photo collections in bulk by selecting layers with attachments and grouping by a match field."
    )
    
    # Show the main UI
    show_bulk_collections_ui()


def show_bulk_collections_ui():
    """Display the main bulk collections UI flow"""
    gis = get_gis_object()
    if not gis:
        return
    
    # Web map selection using ItemSelector
    item_selector = ItemSelector(gis, "Web Map", "bulk_collections")
    selected_webmap = item_selector.show(
        title="Select Web Map",
        default_id=st.session_state.get("bulk_collections_webmap_id", "")
    )
    
    if not selected_webmap:
        return
    
    # Store webmap ID
    st.session_state.bulk_collections_webmap_id = selected_webmap.id
    
    # Session state key for layer data
    layer_data_key = f"bulk_collections_layers_{selected_webmap.id}"
    
    # Load layers button
    col1, col2 = st.columns([1, 3])
    with col1:
        load_layers = st.button("Load Layers", type="secondary", use_container_width=True, key="bulk_load_layers")
    
    # Load or refresh layer data
    if load_layers or layer_data_key not in st.session_state:
        with st.spinner("Loading layers with attachments..."):
            try:
                layer_details = get_webmap_layer_details_with_attachments(selected_webmap, gis)
                if layer_details:
                    st.session_state[layer_data_key] = layer_details
                    st.success(f"Loaded {len(layer_details)} layers with attachments enabled.")
                else:
                    st.warning("No layers with attachments found in this web map.")
                    return
            except Exception as e:
                st.error(f"Failed to load layers: {e}")
                logger.error(f"Error loading layer details: {e}")
                return
    
    # Get layer data from session state
    layer_details = st.session_state.get(layer_data_key, [])
    
    if not layer_details:
        st.info("Click 'Load Layers' to fetch layers with attachments.")
        return
    
    # Display layers in AgGrid table
    st.subheader("Layers with Attachments")
    st.caption("Select the match field for each layer you want to include.")
    
    # Prepare DataFrame for the data editor
    df_data = []
    for layer in layer_details:
        fields_with_types = layer.get("fields_with_types", [])
        fields_json = json.dumps(fields_with_types) if fields_with_types else "[]"
        
        df_data.append({
            "Include": False,
            "Layer Name": layer["name"],
            "Path": layer["path"],
            "Match Field": "",
            "_url": layer["url"],
            "_fields": fields_json
        })
    
    df = pd.DataFrame(df_data)
    
    # Build grid options
    gb = GridOptionsBuilder.from_dataframe(df)
    
    gb.configure_default_column(
        resizable=True,
        sortable=True,
        filter=True,
        minWidth=80
    )
    
    # Checkbox style
    checkbox_cell_style = {"display": "flex", "justifyContent": "center", "alignItems": "center"}
    
    gb.configure_column(
        "Include",
        headerName="Include",
        editable=True,
        cellRenderer="agCheckboxCellRenderer",
        cellEditor="agCheckboxCellEditor",
        width=80,
        minWidth=80,
        headerTooltip="Check to include this layer",
        cellStyle=checkbox_cell_style
    )
    
    gb.configure_column(
        "Layer Name",
        headerName="Layer Name",
        editable=False,
        width=200,
        headerTooltip="Name of the layer in the web map"
    )
    
    gb.configure_column(
        "Path",
        headerName="Path",
        editable=False,
        width=150,
        headerTooltip="Full path including group layers"
    )
    
    # Load the custom cell editor JavaScript
    match_field_editor_js = load_js_file("static/js/dynamic_select_cell_editor.js")
    
    gb.configure_column(
        "Match Field",
        headerName="Match Field",
        editable=True,
        cellEditor=match_field_editor_js,
        width=150,
        headerTooltip="Field to use for grouping features into collections"
    )
    
    # Hide internal columns
    empty_formatter = JsCode("function(params) { return ''; }")
    
    gb.configure_column(
        "_url",
        hide=True,
        valueFormatter=empty_formatter,
        editable=False,
        sortable=False,
        filter=False,
        cellDataType=False
    )
    gb.configure_column(
        "_fields",
        hide=True,
        valueFormatter=empty_formatter,
        editable=False,
        sortable=False,
        filter=False,
        cellDataType=False
    )
    
    grid_options = gb.build()
    
    # Display the AgGrid
    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        height=300,
        fit_columns_on_grid_load=True,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        data_return_mode=DataReturnMode.AS_INPUT,
        theme="streamlit",
        key=f"bulk_collections_grid_{selected_webmap.id}",
        allow_unsafe_jscode=True
    )
    
    # Get edited data
    edited_df = grid_response["data"]
    
    # Summary of selected layers
    selected_rows = edited_df[edited_df["Include"] == True]
    selected_count = len(selected_rows)
    st.markdown(f"**Selected layers:** {selected_count}")
    
    # Validate selection
    validation_errors = []
    if selected_count > 0:
        for idx, row in selected_rows.iterrows():
            if not row["Match Field"]:
                validation_errors.append(f"'{row['Layer Name']}': Match field is required")
    
    if validation_errors:
        st.warning("Please select a match field for all included layers:")
        for error in validation_errors:
            st.caption(f"  - {error}")
    
    # Generate Collections button
    st.divider()
    
    col1, col2 = st.columns([1, 3])
    with col1:
        generate_button = st.button(
            "Generate Collections",
            type="primary",
            use_container_width=True,
            disabled=selected_count == 0 or len(validation_errors) > 0
        )
    
    # Handle generate request
    if generate_button and selected_count > 0 and len(validation_errors) == 0:
        generate_collections(selected_webmap.id, edited_df, gis)


def generate_collections(map_id: str, edited_df: pd.DataFrame, gis) -> None:
    """Generate collections from the selected layers and match fields."""
    
    selected_rows = edited_df[edited_df["Include"] == True]
    
    with st.spinner("Querying features from selected layers..."):
        # Step 1: Query features from each layer
        all_features = []
        layer_info = {}
        
        for idx, row in selected_rows.iterrows():
            layer_url = row["_url"]
            match_field = row["Match Field"]
            layer_name = row["Layer Name"]
            
            st.text(f"Querying {layer_name}...")
            
            features = query_features_by_field(layer_url, match_field, gis)
            
            if features:
                all_features.extend(features)
                layer_info[layer_url] = {
                    "name": layer_name,
                    "match_field": match_field,
                    "feature_count": len(features)
                }
                logger.info(f"Found {len(features)} features in layer '{layer_name}'")
        
        if not all_features:
            st.warning("No features found in the selected layers.")
            return
        
        st.success(f"Found {len(all_features)} total features across {len(layer_info)} layers.")
    
    with st.spinner("Grouping features by match values..."):
        # Step 2: Group features by match values (union - any layer)
        grouped_features = group_features_by_match_values(all_features)
        
        st.success(f"Created {len(grouped_features)} groupings based on common match values.")
    
    with st.spinner("Generating collections payload..."):
        # Step 3: Get attachments and create collections
        collections = generate_collections_payload(map_id, grouped_features, layer_info, gis)
        
        if not collections:
            st.warning("No collections generated. Check if features have attachments.")
            return
    
    # Step 4: Validate payload
    validation_result = validate_collections_payload(collections, map_id)
    
    # Step 5: Display results
    display_collections_payload(collections, validation_result)


def group_features_by_match_values(features: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group features by their match values (union across all layers).
    
    Args:
        features: List of feature dictionaries with match_value, object_id, global_id, layer_url
        
    Returns:
        Dictionary mapping match values to lists of features
    """
    grouped = {}
    
    for feature in features:
        match_value = str(feature.get("match_value", ""))
        if not match_value:
            continue
        
        if match_value not in grouped:
            grouped[match_value] = []
        
        grouped[match_value].append(feature)
    
    logger.info(f"Grouped features into {len(grouped)} unique match values")
    return grouped


def generate_collections_payload(
    map_id: str,
    grouped_features: Dict[str, List[Dict[str, Any]]],
    layer_info: Dict[str, Dict[str, Any]],
    gis
) -> List[Dict[str, Any]]:
    """
    Generate Collection objects with Photo objects for each group.
    
    Args:
        map_id: The web map ID
        grouped_features: Dictionary mapping match values to feature lists
        layer_info: Dictionary with layer URL -> layer info
        gis: The authenticated GIS object
        
    Returns:
        List of Collection dictionaries
    """
    collections = []
    
    # Get all unique layer URLs
    layer_urls = list(layer_info.keys())
    
    # Cache FeatureLayer objects
    feature_layers = {}
    for url in layer_urls:
        fl = get_feature_layer(gis, url)
        if fl:
            feature_layers[url] = fl
    
    # Get all object IDs per layer for batch attachment querying
    layer_oids = {}
    for url in layer_urls:
        layer_oids[url] = set()
    
    for match_value, features in grouped_features.items():
        for feature in features:
            layer_url = feature.get("layer_url")
            if layer_url in layer_oids:
                layer_oids[layer_url].add(feature.get("object_id"))
    
    # Query attachments for all features in each layer (batch)
    layer_attachments = {}
    for url, oids in layer_oids.items():
        if url in feature_layers and oids:
            attachments = get_layer_attachments(feature_layers[url], list(oids))
            layer_attachments[url] = attachments
    
    # Create collections for each match value
    for match_value, features in grouped_features.items():
        photos = []
        photo_order = 1
        
        for feature in features:
            layer_url = feature.get("layer_url")
            object_id = feature.get("object_id")
            global_id = feature.get("global_id", "")
            
            # Get attachments for this feature
            feature_attachments = layer_attachments.get(layer_url, {}).get(object_id, [])
            
            # Create a Photo object for each attachment
            for attachment in feature_attachments:
                photos.append({
                    "layer_id": layer_url,
                    "global_id": global_id,
                    "object_id": object_id,
                    "photo_order": photo_order
                })
                photo_order += 1
        
        # Only create collection if there are photos
        if photos:
            collection = {
                "collection_name": str(match_value),
                "map_id": map_id,
                "photos": photos
            }
            collections.append(collection)
    
    logger.info(f"Generated {len(collections)} collections with photos")
    return collections


def validate_collections_payload(
    collections: List[Dict[str, Any]],
    expected_map_id: str
) -> Dict[str, Any]:
    """
    Validate the collections payload structure.
    
    Args:
        collections: List of Collection dictionaries
        expected_map_id: The expected map ID
        
    Returns:
        Dictionary with validation results:
        - valid: bool
        - errors: List of error messages
        - warnings: List of warning messages
        - stats: Dictionary with summary statistics
    """
    errors = []
    warnings = []
    
    total_photos = 0
    empty_collections = 0
    
    for i, collection in enumerate(collections):
        collection_name = collection.get("collection_name", f"Collection {i}")
        
        # Check required fields
        if not collection.get("collection_name"):
            errors.append(f"Collection {i}: collection_name is required")
        elif len(collection.get("collection_name", "")) > 100:
            errors.append(f"Collection {i}: collection_name exceeds 100 characters")
        
        if not collection.get("map_id"):
            errors.append(f"'{collection_name}': map_id is required")
        elif collection.get("map_id") != expected_map_id:
            errors.append(f"'{collection_name}': map_id doesn't match selected web map")
        
        # Check photos
        photos = collection.get("photos", [])
        if not photos:
            warnings.append(f"'{collection_name}': No photos in collection")
            empty_collections += 1
        else:
            total_photos += len(photos)
            
            for j, photo in enumerate(photos):
                if not photo.get("layer_id"):
                    errors.append(f"'{collection_name}' Photo {j}: layer_id is required")
                if not photo.get("global_id"):
                    warnings.append(f"'{collection_name}' Photo {j}: global_id is empty")
                if photo.get("object_id") is None:
                    errors.append(f"'{collection_name}' Photo {j}: object_id is required")
                if photo.get("photo_order") is None:
                    errors.append(f"'{collection_name}' Photo {j}: photo_order is required")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "stats": {
            "total_collections": len(collections),
            "total_photos": total_photos,
            "empty_collections": empty_collections
        }
    }


def display_collections_payload(
    collections: List[Dict[str, Any]],
    validation_result: Dict[str, Any]
) -> None:
    """Display the collections payload with validation status and copy functionality."""
    
    st.divider()
    st.subheader("Generated Collections Payload")
    
    # Show stats
    stats = validation_result.get("stats", {})
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Collections", stats.get("total_collections", 0))
    with col2:
        st.metric("Total Photos", stats.get("total_photos", 0))
    with col3:
        st.metric("Empty Collections", stats.get("empty_collections", 0))
    
    # Show validation status
    if validation_result.get("valid"):
        st.success("Payload validation passed!")
    else:
        st.error("Payload validation failed!")
        with st.expander("Validation Errors", expanded=True):
            for error in validation_result.get("errors", []):
                st.error(f"- {error}")
    
    if validation_result.get("warnings"):
        with st.expander("Warnings", expanded=False):
            for warning in validation_result.get("warnings", []):
                st.warning(f"- {warning}")
    
    # Show groupings summary
    st.subheader("Groupings")
    groupings_df = pd.DataFrame([
        {
            "Collection Name": c.get("collection_name", ""),
            "Photo Count": len(c.get("photos", []))
        }
        for c in collections
    ])
    st.dataframe(groupings_df, use_container_width=True, hide_index=True)
    
    # Show JSON payload
    st.subheader("JSON Payload")
    st.caption("Copy the JSON below to use with the API endpoint.")
    
    # Convert to JSON string
    payload_json = json.dumps(collections, indent=2)
    
    # Display in a code block with copy button
    st.code(payload_json, language="json")
    
    # Also provide as downloadable text
    st.download_button(
        label="Download JSON",
        data=payload_json,
        file_name="collections_payload.json",
        mime="application/json"
    )
