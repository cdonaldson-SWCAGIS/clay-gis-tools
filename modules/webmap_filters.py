import streamlit as st
import logging
import sys
import os
from typing import List, Optional

# Configure logging
logger = logging.getLogger("webmap_filters")

# Import the patch_webmap_filters module
try:
    from src import patch_webmap_filters
except ImportError:
    st.error("Failed to import patch_webmap_filters module. Make sure the src directory is in your Python path.")
    sys.exit(1)

def show():
    """Display the Web Map Filters interface"""
    st.title("Web Map Filters")
    
    # Check authentication
    if not st.session_state.authenticated:
        st.warning("Please authenticate first")
        st.info("Use the navigation sidebar to go to the Authentication page")
        return
    
    # Display information about the tool
    st.markdown("""
    ## Web Map Filter Utility
    
    This tool allows you to update definition expressions (filters) in ArcGIS web maps.
    It will identify all layers containing a specific field and apply a new filter expression to them.
    """)
    
    # Create tabs for different operations
    tab1, tab2 = st.tabs(["Update Filters", "Advanced Options"])
    
    with tab1:
        show_update_filters()
    
    with tab2:
        show_advanced_options()
    
    # Show help information
    show_help()

def show_update_filters():
    """Display the main filter update interface"""
    # Web map selection
    st.subheader("Web Map Selection")
    
    # Option to search for web maps
    use_search = st.checkbox("Search for web maps", value=False)
    
    if use_search:
        # Search for web maps
        search_query = st.text_input("Search query", placeholder="Enter search terms")
        
        if search_query:
            with st.spinner("Searching for web maps..."):
                try:
                    # Search for web maps using the GIS object
                    items = st.session_state.gis.content.search(
                        query=search_query, 
                        item_type="Web Map",
                        max_items=25
                    )
                    
                    if items:
                        # Create a dictionary of web map titles and IDs
                        options = {f"{item.title} ({item.id})": item.id for item in items}
                        
                        # Create a selectbox for the user to choose a web map
                        selected = st.selectbox(
                            "Select a web map",
                            list(options.keys()),
                            index=None,
                            placeholder="Choose a web map..."
                        )
                        
                        if selected:
                            webmap_id = options[selected]
                            st.session_state.webmap_id = webmap_id
                    else:
                        st.info("No web maps found matching your search criteria")
                except Exception as e:
                    st.error(f"Error searching for web maps: {str(e)}")
                    logger.error(f"Error searching for web maps: {str(e)}")
    else:
        # Direct ID input
        webmap_id = st.text_input(
            "Web Map ID",
            value=st.session_state.get("webmap_id", ""),
            placeholder="Enter the web map item ID"
        )
        
        if webmap_id:
            st.session_state.webmap_id = webmap_id
    
    # Filter parameters
    st.subheader("Filter Parameters")
    
    # Target field
    target_field = st.text_input(
        "Target Field",
        value=st.session_state.get("target_field", "project_number"),
        help="The field name to search for in layers"
    )
    
    if target_field:
        st.session_state.target_field = target_field
    
    # New filter expression
    new_filter = st.text_area(
        "New Filter Expression",
        value=st.session_state.get("new_filter", "project_number = '123456'"),
        help="The SQL expression to apply to matching layers"
    )
    
    if new_filter:
        st.session_state.new_filter = new_filter
    
    # Debug mode
    debug_mode = st.checkbox(
        "Debug Mode (simulate updates)",
        value=st.session_state.get("debug_mode", True),
        help="When enabled, changes will be simulated but not saved to the server"
    )
    
    st.session_state.debug_mode = debug_mode
    
    # Execute button
    col1, col2 = st.columns([1, 3])
    with col1:
        update_button = st.button("Update Web Map Filters", type="primary", use_container_width=True)
    
    # Handle update request
    if update_button:
        if not st.session_state.get("webmap_id"):
            st.error("Please provide a Web Map ID")
        elif not target_field:
            st.error("Please provide a Target Field")
        elif not new_filter:
            st.error("Please provide a Filter Expression")
        else:
            # Execute the update
            execute_filter_update(st.session_state.webmap_id, target_field, new_filter, debug_mode)

def show_advanced_options():
    """Display advanced options for filter updates"""
    st.subheader("Advanced Options")
    
    # Batch processing
    st.markdown("### Batch Processing")
    st.markdown("""
    You can update multiple web maps at once by providing a list of web map IDs.
    Each web map will be processed with the same target field and filter expression.
    """)
    
    # Web map IDs
    webmap_ids = st.text_area(
        "Web Map IDs (one per line)",
        placeholder="Enter web map IDs, one per line"
    )
    
    # Target field and filter (same as in the main tab)
    batch_target_field = st.text_input(
        "Target Field",
        value=st.session_state.get("target_field", "project_number")
    )
    
    batch_new_filter = st.text_area(
        "New Filter Expression",
        value=st.session_state.get("new_filter", "project_number = '123456'")
    )
    
    # Debug mode
    batch_debug_mode = st.checkbox(
        "Debug Mode (simulate updates)",
        value=st.session_state.get("debug_mode", True)
    )
    
    # Execute batch button
    col1, col2 = st.columns([1, 3])
    with col1:
        batch_button = st.button("Run Batch Update", type="primary", use_container_width=True)
    
    # Handle batch update request
    if batch_button:
        if not webmap_ids:
            st.error("Please provide at least one Web Map ID")
        elif not batch_target_field:
            st.error("Please provide a Target Field")
        elif not batch_new_filter:
            st.error("Please provide a Filter Expression")
        else:
            # Parse web map IDs
            ids = [id.strip() for id in webmap_ids.split("\n") if id.strip()]
            
            if not ids:
                st.error("No valid Web Map IDs provided")
            else:
                # Execute batch update
                execute_batch_filter_update(ids, batch_target_field, batch_new_filter, batch_debug_mode)

def execute_filter_update(webmap_id: str, target_field: str, new_filter: str, debug_mode: bool) -> None:
    """
    Execute a filter update on a single web map
    
    Args:
        webmap_id: The ID of the web map to update
        target_field: The field name to search for in layers
        new_filter: The SQL expression to apply to matching layers
        debug_mode: Whether to simulate updates without saving changes
    """
    # Create a status container
    status = st.empty()
    status.info("Starting update process...")
    
    # Create a progress bar
    progress_bar = st.progress(0)
    
    try:
        # Set debug mode
        patch_webmap_filters.DEBUG_MODE = debug_mode
        
        # Update progress
        progress_bar.progress(25)
        status.info("Retrieving web map...")
        
        # Get the web map item
        webmap_item = patch_webmap_filters.get_webmap_item(webmap_id)
        
        if not webmap_item:
            status.error(f"Web map with ID {webmap_id} was not found")
            progress_bar.empty()
            return
        
        # Update progress
        progress_bar.progress(50)
        status.info(f"Processing web map: {webmap_item.title}...")
        
        # Update the web map
        updated_layers = patch_webmap_filters.update_webmap_definition_by_field(
            webmap_id, target_field, new_filter
        )
        
        # Update progress
        progress_bar.progress(100)
        
        # Display results
        if updated_layers:
            status.success(f"Successfully updated {len(updated_layers)} layers")
            
            # Show layer details
            st.subheader("Updated Layers")
            for i, layer_url in enumerate(updated_layers, 1):
                st.write(f"{i}. {layer_url}")
            
            if debug_mode:
                st.info("Running in DEBUG mode - changes were simulated and not saved to the server")
            else:
                st.success("Changes were verified and saved to the server")
        else:
            status.warning("No layers were updated")
            
            if not debug_mode:
                st.error(
                    "Possible issues:\n"
                    "  • The web map may not contain layers with the target field\n"
                    "  • The server may not have accepted the changes\n"
                    "  • There might be permission issues with the web map"
                )
                
                st.info("Try running with Debug Mode enabled to see more details")
    except Exception as e:
        status.error(f"Error updating web map: {str(e)}")
        logger.error(f"Error updating web map {webmap_id}: {str(e)}")
        progress_bar.empty()

def execute_batch_filter_update(webmap_ids: List[str], target_field: str, new_filter: str, debug_mode: bool) -> None:
    """
    Execute a filter update on multiple web maps
    
    Args:
        webmap_ids: List of web map IDs to update
        target_field: The field name to search for in layers
        new_filter: The SQL expression to apply to matching layers
        debug_mode: Whether to simulate updates without saving changes
    """
    # Set debug mode
    patch_webmap_filters.DEBUG_MODE = debug_mode
    
    # Create a status container
    status = st.empty()
    status.info(f"Starting batch update for {len(webmap_ids)} web maps...")
    
    # Create a progress bar
    progress_bar = st.progress(0)
    
    # Create an expander for detailed results
    with st.expander("Batch Update Results", expanded=True):
        results_container = st.container()
    
    # Track results
    successful_updates = 0
    failed_updates = 0
    total_layers_updated = 0
    results = {}
    
    # Process each web map
    for i, webmap_id in enumerate(webmap_ids):
        # Update progress
        progress = int((i / len(webmap_ids)) * 100)
        progress_bar.progress(progress)
        status.info(f"Processing web map {i+1} of {len(webmap_ids)}: {webmap_id}")
        
        try:
            # Get the web map item
            webmap_item = patch_webmap_filters.get_webmap_item(webmap_id)
            
            if not webmap_item:
                with results_container:
                    st.error(f"Web map with ID {webmap_id} was not found")
                failed_updates += 1
                results[webmap_id] = {"status": "error", "message": "Web map not found"}
                continue
            
            # Update the web map
            updated_layers = patch_webmap_filters.update_webmap_definition_by_field(
                webmap_id, target_field, new_filter
            )
            
            # Record results
            if updated_layers:
                successful_updates += 1
                total_layers_updated += len(updated_layers)
                results[webmap_id] = {
                    "status": "success",
                    "title": webmap_item.title,
                    "layers_updated": len(updated_layers),
                    "layer_urls": updated_layers
                }
                
                with results_container:
                    st.success(f"Web map '{webmap_item.title}' ({webmap_id}): Updated {len(updated_layers)} layers")
            else:
                failed_updates += 1
                results[webmap_id] = {
                    "status": "warning",
                    "title": webmap_item.title,
                    "message": "No layers were updated"
                }
                
                with results_container:
                    st.warning(f"Web map '{webmap_item.title}' ({webmap_id}): No layers were updated")
        
        except Exception as e:
            failed_updates += 1
            results[webmap_id] = {"status": "error", "message": str(e)}
            
            with results_container:
                st.error(f"Error processing web map {webmap_id}: {str(e)}")
            
            logger.error(f"Error processing web map {webmap_id} in batch update: {str(e)}")
    
    # Update progress to completion
    progress_bar.progress(100)
    
    # Display summary
    status.success(f"Batch update completed: {successful_updates} successful, {failed_updates} failed, {total_layers_updated} total layers updated")
    
    # Display debug mode notice
    if debug_mode:
        st.info("Running in DEBUG mode - changes were simulated and not saved to the server")
    else:
        st.success("Changes were verified and saved to the server")
    
    # Detailed summary
    st.subheader("Batch Update Summary")
    st.write(f"- **Web Maps Processed:** {len(webmap_ids)}")
    st.write(f"- **Successful Updates:** {successful_updates}")
    st.write(f"- **Failed Updates:** {failed_updates}")
    st.write(f"- **Total Layers Updated:** {total_layers_updated}")

def show_help():
    """Display help information for the Web Map Filters tool"""
    with st.expander("Need Help?"):
        st.markdown("""
        ### Web Map Filters Help
        
        #### Target Field
        The target field is the field name that the tool will look for in each layer.
        Only layers that contain this field will be updated.
        
        Common field names include:
        - `project_number` - Project identifier
        - `status` - Status field
        - `created_date` - Creation date
        
        #### Filter Expression
        The filter expression is an SQL WHERE clause that will be applied to matching layers.
        
        Examples:
        - `project_number = '123456'` - Exact match
        - `status IN ('Active', 'Pending')` - Multiple values
        - `created_date > '2023-01-01'` - Date comparison
        
        #### Debug Mode
        When Debug Mode is enabled, the tool will simulate updates without actually saving changes to the server.
        This is useful for testing and validation.
        
        #### Troubleshooting
        - Ensure your web map ID is correct
        - Verify that the target field exists in at least one layer
        - Check that your filter expression uses valid SQL syntax
        - Try running in Debug Mode to see more details
        """)
