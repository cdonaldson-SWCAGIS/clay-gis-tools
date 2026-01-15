"""
UI components for item and field selection.
Reusable Streamlit components for selecting ArcGIS items and fields.
"""

import streamlit as st
import logging
from typing import List, Optional, Dict, Any, Tuple
from arcgis.gis import GIS, Item
from arcgis.features import FeatureLayer

from backend.utils.logging import get_logger
from backend.core.webmap.utils import (
    get_webmap_item as get_webmap_item_util,
    get_feature_layer,
    get_layer_fields_from_feature_layer,
    layer_contains_field
)
from backend.utils.exceptions import WebMapNotFoundError, InvalidWebMapError

logger = get_logger("item_selector")


class ItemSelector:
    """
    A reusable component for selecting ArcGIS items with consistent UI/UX.
    Supports both search-based selection and direct ID input.
    """
    
    def __init__(self, gis: GIS, item_type: str = "Web Map", key_prefix: str = "item"):
        """
        Initialize the ItemSelector.
        
        Args:
            gis: The authenticated GIS object
            item_type: The type of item to search for (e.g., "Web Map", "Feature Layer")
            key_prefix: Unique prefix for Streamlit widget keys
        """
        self.gis = gis
        self.item_type = item_type
        self.key_prefix = key_prefix
        self.session_key_id = f"{key_prefix}_id"
        self.session_key_item = f"{key_prefix}_item"
    
    def show(self, 
             title: str = None,
             help_text: str = None,
             default_id: str = "",
             max_search_results: int = 25,
             show_item_details: bool = True) -> Optional[Item]:
        """
        Display the item selection interface.
        
        Args:
            title: Title for the selection section
            help_text: Help text to display
            default_id: Default item ID to populate
            max_search_results: Maximum number of search results to show
            show_item_details: Whether to show item details when selected
            
        Returns:
            Selected Item object or None if no item is selected
        """
        if title:
            st.subheader(title)
        
        if help_text:
            st.info(help_text)
        
        # Selection method
        use_search = st.checkbox(
            f"Search for {self.item_type.lower()}s", 
            value=False,
            key=f"{self.key_prefix}_use_search"
        )
        
        selected_item = None
        
        if use_search:
            selected_item = self._show_search_interface(max_search_results)
        else:
            selected_item = self._show_direct_input_interface(default_id)
        
        # Show item details if selected
        if selected_item and show_item_details:
            self._show_item_details(selected_item)
        
        # Store in session state
        if selected_item:
            st.session_state[self.session_key_item] = selected_item
            st.session_state[self.session_key_id] = selected_item.id
        
        return selected_item
    
    def _show_search_interface(self, max_results: int) -> Optional[Item]:
        """Show the search-based selection interface."""
        search_query = st.text_input(
            "Search query", 
            placeholder="Enter search terms",
            key=f"{self.key_prefix}_search_query"
        )
        
        if search_query:
            with st.spinner(f"Searching for {self.item_type.lower()}s..."):
                try:
                    items = self.gis.content.search(
                        query=search_query,
                        item_type=self.item_type,
                        max_items=max_results
                    )
                    
                    if items:
                        # Create options with title and ID
                        options = {}
                        for item in items:
                            display_name = f"{item.title}"
                            if hasattr(item, 'owner'):
                                display_name += f" (by {item.owner})"
                            display_name += f" - {item.id}"
                            options[display_name] = item
                        
                        selected_display = st.selectbox(
                            f"Select a {self.item_type.lower()}",
                            list(options.keys()),
                            index=None,
                            placeholder=f"Choose a {self.item_type.lower()}...",
                            key=f"{self.key_prefix}_search_select"
                        )
                        
                        if selected_display:
                            return options[selected_display]
                    else:
                        st.info(f"No {self.item_type.lower()}s found matching your search criteria")
                        
                except Exception as e:
                    st.error(f"Error searching for {self.item_type.lower()}s: {str(e)}")
                    logger.error(f"Error searching for {self.item_type}s: {str(e)}")
        
        return None
    
    def _show_direct_input_interface(self, default_id: str) -> Optional[Item]:
        """Show the direct ID input interface."""
        item_id = st.text_input(
            f"{self.item_type} ID",
            value=st.session_state.get(self.session_key_id, default_id),
            placeholder=f"Enter the {self.item_type.lower()} item ID",
            key=f"{self.key_prefix}_direct_input"
        )
        
        if item_id:
            # Validate and retrieve the item
            try:
                item = self.gis.content.get(item_id)
                if item and item.type == self.item_type:
                    return item
                elif item:
                    st.error(f"Item {item_id} is not a {self.item_type} (found: {item.type})")
                else:
                    st.error(f"{self.item_type} with ID {item_id} was not found")
            except Exception as e:
                st.error(f"Error retrieving {self.item_type.lower()}: {str(e)}")
                logger.error(f"Error retrieving {self.item_type} {item_id}: {str(e)}")
        
        return None
    
    def _show_item_details(self, item: Item) -> None:
        """Show details about the selected item."""
        with st.expander(f"{self.item_type} Details", expanded=False):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Title:** {item.title}")
                st.write(f"**ID:** {item.id}")
                st.write(f"**Type:** {item.type}")
                if hasattr(item, 'owner'):
                    st.write(f"**Owner:** {item.owner}")
            
            with col2:
                if hasattr(item, 'created'):
                    if item.created:
                        if isinstance(item.created, (int, float)):
                            from datetime import datetime
                            # Assume milliseconds if > 1e10, seconds otherwise
                            ts = item.created / 1000 if item.created > 1e10 else item.created
                            created_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                        elif hasattr(item.created, 'strftime'):
                            created_date = item.created.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            created_date = str(item.created)
                    else:
                        created_date = "Unknown"
                    st.write(f"**Created:** {created_date}")
                if hasattr(item, 'modified'):
                    if item.modified:
                        if isinstance(item.modified, (int, float)):
                            from datetime import datetime
                            # Assume milliseconds if > 1e10, seconds otherwise
                            ts = item.modified / 1000 if item.modified > 1e10 else item.modified
                            modified_date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                        elif hasattr(item.modified, 'strftime'):
                            modified_date = item.modified.strftime("%Y-%m-%d %H:%M:%S")
                        else:
                            modified_date = str(item.modified)
                    else:
                        modified_date = "Unknown"
                    st.write(f"**Modified:** {modified_date}")
                if hasattr(item, 'numViews'):
                    st.write(f"**Views:** {item.numViews}")
            
            if hasattr(item, 'description') and item.description:
                st.write(f"**Description:** {item.description}")


def get_webmap_item(gis: GIS, webmap_item_id: str) -> Optional[Item]:
    """
    Retrieve a web map item with error handling and logging.
    
    Args:
        gis: The authenticated GIS object
        webmap_item_id: The ID of the web map to retrieve
        
    Returns:
        Web map Item object or None if not found
    """
    try:
        return get_webmap_item_util(webmap_item_id, gis)
    except (WebMapNotFoundError, InvalidWebMapError) as e:
        logger.error(str(e))
        return None
    except Exception as e:
        logger.error(f"Error retrieving web map: {e}")
        return None


class FieldSelector:
    """
    A reusable component for selecting fields from layers.
    """
    
    def __init__(self, key_prefix: str = "field"):
        """
        Initialize the FieldSelector.
        
        Args:
            key_prefix: Unique prefix for Streamlit widget keys
        """
        self.key_prefix = key_prefix
    
    def show(self, 
             feature_layer: FeatureLayer,
             title: str = "Field Selection",
             help_text: str = None,
             field_types: List[str] = None,
             allow_manual_input: bool = True) -> Optional[str]:
        """
        Display the field selection interface.
        
        Args:
            feature_layer: The FeatureLayer to get fields from
            title: Title for the selection section
            help_text: Help text to display
            field_types: List of field types to filter by (e.g., ['esriFieldTypeString'])
            allow_manual_input: Whether to allow manual field name input
            
        Returns:
            Selected field name or None
        """
        if title:
            st.subheader(title)
        
        if help_text:
            st.info(help_text)
        
        if not feature_layer:
            st.error("No feature layer provided")
            return None
        
        # Get fields from the layer
        fields = get_layer_fields_from_feature_layer(feature_layer)
        
        if not fields:
            st.error("No fields found in the layer")
            return None
        
        # Filter fields by type if specified
        if field_types:
            fields = [f for f in fields if f.get("type") in field_types]
        
        # Create field options
        field_options = {}
        for field in fields:
            field_name = field.get("name", "")
            field_type = field.get("type", "")
            field_alias = field.get("alias", field_name)
            
            display_name = f"{field_alias} ({field_name})"
            if field_type:
                display_name += f" - {field_type}"
            
            field_options[display_name] = field_name
        
        # Selection method
        if allow_manual_input:
            use_dropdown = st.checkbox(
                "Select from available fields",
                value=True,
                key=f"{self.key_prefix}_use_dropdown"
            )
        else:
            use_dropdown = True
        
        selected_field = None
        
        if use_dropdown:
            if field_options:
                selected_display = st.selectbox(
                    "Select a field",
                    list(field_options.keys()),
                    index=None,
                    placeholder="Choose a field...",
                    key=f"{self.key_prefix}_dropdown"
                )
                
                if selected_display:
                    selected_field = field_options[selected_display]
            else:
                st.warning("No fields available for selection")
        else:
            selected_field = st.text_input(
                "Field name",
                placeholder="Enter the field name",
                key=f"{self.key_prefix}_manual"
            )
        
        return selected_field


def show_operation_status(operation_name: str, 
                         total_items: int = None,
                         current_item: int = None,
                         current_item_name: str = None,
                         status_message: str = None) -> Tuple[Any, Any]:
    """
    Show a consistent status display for long-running operations.
    
    Args:
        operation_name: Name of the operation being performed
        total_items: Total number of items to process
        current_item: Current item number (1-based)
        current_item_name: Name of the current item being processed
        status_message: Custom status message
        
    Returns:
        Tuple of (status_container, progress_bar) for updating
    """
    # Create status container
    status_container = st.empty()
    
    # Create progress bar if total items specified
    progress_bar = None
    if total_items and total_items > 1:
        progress_bar = st.progress(0)
    
    # Set initial status
    if status_message:
        status_container.info(status_message)
    elif current_item and total_items:
        if current_item_name:
            status_container.info(f"{operation_name}: Processing item {current_item} of {total_items} - {current_item_name}")
        else:
            status_container.info(f"{operation_name}: Processing item {current_item} of {total_items}")
    else:
        status_container.info(f"Starting {operation_name}...")
    
    return status_container, progress_bar


def update_operation_status(status_container: Any,
                           progress_bar: Any,
                           operation_name: str,
                           total_items: int = None,
                           current_item: int = None,
                           current_item_name: str = None,
                           status_message: str = None,
                           progress_percent: int = None) -> None:
    """
    Update the status display for a long-running operation.
    
    Args:
        status_container: The status container returned by show_operation_status
        progress_bar: The progress bar returned by show_operation_status
        operation_name: Name of the operation being performed
        total_items: Total number of items to process
        current_item: Current item number (1-based)
        current_item_name: Name of the current item being processed
        status_message: Custom status message
        progress_percent: Progress percentage (0-100)
    """
    # Update status message
    if status_message:
        status_container.info(status_message)
    elif current_item and total_items:
        if current_item_name:
            status_container.info(f"{operation_name}: Processing item {current_item} of {total_items} - {current_item_name}")
        else:
            status_container.info(f"{operation_name}: Processing item {current_item} of {total_items}")
    
    # Update progress bar
    if progress_bar:
        if progress_percent is not None:
            progress_bar.progress(progress_percent)
        elif current_item and total_items:
            progress = int((current_item / total_items) * 100)
            progress_bar.progress(progress)


def complete_operation_status(status_container: Any,
                             progress_bar: Any,
                             operation_name: str,
                             success: bool,
                             message: str = None,
                             details: Dict[str, Any] = None) -> None:
    """
    Complete the status display for a long-running operation.
    
    Args:
        status_container: The status container returned by show_operation_status
        progress_bar: The progress bar returned by show_operation_status
        operation_name: Name of the operation being performed
        success: Whether the operation was successful
        message: Custom completion message
        details: Additional details to display
    """
    # Complete progress bar
    if progress_bar:
        progress_bar.progress(100)
    
    # Set completion status
    if message:
        if success:
            status_container.success(message)
        else:
            status_container.error(message)
    else:
        if success:
            status_container.success(f"{operation_name} completed successfully")
        else:
            status_container.error(f"{operation_name} failed")
    
    # Show details if provided
    if details:
        with st.expander("Operation Details", expanded=False):
            for key, value in details.items():
                st.write(f"**{key}:** {value}")
