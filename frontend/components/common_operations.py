"""
Common operations and utilities shared across all GIS tools.
Provides consistent patterns for authentication, debug mode, and operation execution.
"""

import streamlit as st
import logging
import os
from typing import Dict, Any, List, Optional, Callable, Union, Tuple
from arcgis.gis import GIS

from backend.utils.logging import get_logger

# Configure logging
logger = get_logger("common_operations")


def ensure_authentication() -> bool:
    """
    Ensure the user is authenticated. Show warning if not.
    
    Returns:
        True if authenticated, False otherwise
    """
    if not st.session_state.get("authenticated", False):
        st.warning("Please authenticate first")
        st.info("Use the navigation sidebar to go to the Authentication page")
        return False
    return True


def get_gis_object() -> Optional[GIS]:
    """
    Get the authenticated GIS object from session state.
    
    Returns:
        GIS object if authenticated, None otherwise
    """
    if not ensure_authentication():
        return None
    
    return st.session_state.get("gis")


def show_debug_mode_control(key_prefix: str = "debug") -> bool:
    """
    Show a consistent debug mode control and return the current setting.
    
    Args:
        key_prefix: Unique prefix for the widget key
        
    Returns:
        Current debug mode setting
    """
    debug_mode = st.checkbox(
        "Debug Mode (simulate updates)",
        value=st.session_state.get("debug_mode", True),
        help="When enabled, changes will be simulated but not saved to the server",
        key=f"{key_prefix}_mode"
    )
    
    # Update session state
    st.session_state.debug_mode = debug_mode
    
    return debug_mode


def show_operation_parameters(
    title: str = "Operation Parameters",
    parameters: List[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Show a consistent interface for operation parameters.
    
    Args:
        title: Title for the parameters section
        parameters: List of parameter definitions
        
    Returns:
        Dictionary of parameter values
    """
    if title:
        st.subheader(title)
    
    if not parameters:
        return {}
    
    param_values = {}
    
    for param in parameters:
        param_name = param.get("name", "")
        param_type = param.get("type", "text")
        param_label = param.get("label", param_name)
        param_help = param.get("help", "")
        param_default = param.get("default", "")
        param_placeholder = param.get("placeholder", "")
        param_key = param.get("key", param_name)
        param_required = param.get("required", False)
        param_options = param.get("options", [])
        
        # Get current value from session state
        session_key = f"param_{param_key}"
        current_value = st.session_state.get(session_key, param_default)
        
        # Show the appropriate input widget
        if param_type == "text":
            value = st.text_input(
                param_label,
                value=current_value,
                placeholder=param_placeholder,
                help=param_help,
                key=session_key
            )
        elif param_type == "textarea":
            value = st.text_area(
                param_label,
                value=current_value,
                placeholder=param_placeholder,
                help=param_help,
                key=session_key
            )
        elif param_type == "number":
            min_value = param.get("min_value", None)
            max_value = param.get("max_value", None)
            step = param.get("step", 1)
            value = st.number_input(
                param_label,
                value=current_value if current_value else 0,
                min_value=min_value,
                max_value=max_value,
                step=step,
                help=param_help,
                key=session_key
            )
        elif param_type == "selectbox":
            index = 0
            if current_value and current_value in param_options:
                index = param_options.index(current_value)
            value = st.selectbox(
                param_label,
                param_options,
                index=index,
                help=param_help,
                key=session_key
            )
        elif param_type == "checkbox":
            value = st.checkbox(
                param_label,
                value=bool(current_value),
                help=param_help,
                key=session_key
            )
        else:
            # Default to text input
            value = st.text_input(
                param_label,
                value=current_value,
                placeholder=param_placeholder,
                help=param_help,
                key=session_key
            )
        
        # Validate required fields
        if param_required and not value:
            st.error(f"{param_label} is required")
        
        param_values[param_name] = value
    
    return param_values


def validate_operation_inputs(
    inputs: Dict[str, Any],
    required_fields: List[str] = None
) -> Tuple[bool, List[str]]:
    """
    Validate operation inputs and return validation status.
    
    Args:
        inputs: Dictionary of input values
        required_fields: List of required field names
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    if not required_fields:
        required_fields = []
    
    errors = []
    
    for field in required_fields:
        if field not in inputs or not inputs[field]:
            errors.append(f"{field} is required")
    
    return len(errors) == 0, errors


def show_validation_errors(errors: List[str]) -> None:
    """
    Display validation errors in a consistent format.
    
    Args:
        errors: List of error messages
    """
    if errors:
        st.error("Please fix the following errors:")
        for error in errors:
            st.write(f"• {error}")


def execute_operation_with_status(
    operation_name: str,
    operation_func: Callable,
    operation_args: tuple = (),
    operation_kwargs: dict = None,
    success_message: str = None,
    error_message: str = None,
    show_debug_notice: bool = True
) -> Any:
    """
    Execute an operation with consistent status display and error handling.
    
    Args:
        operation_name: Name of the operation for display
        operation_func: Function to execute
        operation_args: Arguments to pass to the function
        operation_kwargs: Keyword arguments to pass to the function
        success_message: Custom success message
        error_message: Custom error message
        show_debug_notice: Whether to show debug mode notice
        
    Returns:
        Result of the operation function
    """
    if operation_kwargs is None:
        operation_kwargs = {}
    
    # Create status container
    status_container = st.empty()
    status_container.info(f"Starting {operation_name}...")
    
    # Create progress bar
    progress_bar = st.progress(0)
    
    try:
        # Update progress
        progress_bar.progress(25)
        status_container.info(f"Executing {operation_name}...")
        
        # Execute the operation
        result = operation_func(*operation_args, **operation_kwargs)
        
        # Update progress
        progress_bar.progress(100)
        
        # Show success message
        if success_message:
            status_container.success(success_message)
        else:
            status_container.success(f"{operation_name} completed successfully")
        
        # Show debug notice if applicable
        if show_debug_notice and st.session_state.get("debug_mode", True):
            st.info("Running in DEBUG mode - changes were simulated and not saved to the server")
        elif show_debug_notice:
            st.success("Changes were verified and saved to the server")
        
        return result
        
    except Exception as e:
        # Update progress and show error
        progress_bar.empty()
        
        if error_message:
            status_container.error(f"{error_message}: {str(e)}")
        else:
            status_container.error(f"Error in {operation_name}: {str(e)}")
        
        logger.error(f"Error in {operation_name}: {str(e)}")
        return None


def show_operation_results(
    operation_name: str,
    results: Any,
    success_criteria: Callable[[Any], bool] = None,
    result_formatter: Callable[[Any], Dict[str, Any]] = None,
    show_raw_results: bool = False
) -> None:
    """
    Display operation results in a consistent format.
    
    Args:
        operation_name: Name of the operation
        results: Results from the operation
        success_criteria: Function to determine if results indicate success
        result_formatter: Function to format results for display
        show_raw_results: Whether to show raw results in an expander
    """
    if results is None:
        st.error(f"{operation_name} failed - no results returned")
        return
    
    # Determine success
    if success_criteria:
        is_success = success_criteria(results)
    else:
        # Default success criteria
        if isinstance(results, (list, dict)):
            is_success = len(results) > 0
        else:
            is_success = bool(results)
    
    # Format results for display
    if result_formatter:
        formatted_results = result_formatter(results)
    else:
        # Default formatting
        if isinstance(results, list):
            formatted_results = {
                "Items Processed": len(results),
                "Results": results
            }
        elif isinstance(results, dict):
            formatted_results = results
        else:
            formatted_results = {"Result": str(results)}
    
    # Show results
    if is_success:
        st.subheader(f"{operation_name} Results")
        
        # Show formatted results
        for key, value in formatted_results.items():
            if isinstance(value, list) and len(value) > 0:
                st.write(f"**{key}:** {len(value)} items")
                with st.expander(f"View {key}", expanded=False):
                    for i, item in enumerate(value, 1):
                        st.write(f"{i}. {item}")
            else:
                st.write(f"**{key}:** {value}")
    else:
        st.warning(f"{operation_name} completed but no items were processed")
        
        # Show troubleshooting tips
        if not st.session_state.get("debug_mode", True):
            st.error(
                "Possible issues:\n"
                "• The target items may not exist or be accessible\n"
                "• The server may not have accepted the changes\n"
                "• There might be permission issues\n"
                "• The operation parameters may be incorrect"
            )
            st.info("Try running with Debug Mode enabled to see more details")
    
    # Show raw results if requested
    if show_raw_results:
        with st.expander("Raw Results", expanded=False):
            st.json(results)


def show_batch_operation_interface(
    operation_name: str,
    item_type: str = "items",
    item_input_help: str = None
) -> Optional[List[str]]:
    """
    Show a consistent interface for batch operations.
    
    Args:
        operation_name: Name of the operation
        item_type: Type of items being processed
        item_input_help: Help text for item input
        
    Returns:
        List of item IDs or None if no valid items
    """
    st.subheader(f"Batch {operation_name}")
    
    if not item_input_help:
        item_input_help = f"Enter {item_type} IDs, one per line"
    
    st.markdown(f"""
    You can process multiple {item_type} at once by providing a list of IDs.
    Each {item_type.rstrip('s')} will be processed with the same parameters.
    """)
    
    # Item IDs input
    item_ids_text = st.text_area(
        f"{item_type.title()} IDs (one per line)",
        placeholder=item_input_help,
        key=f"batch_{operation_name.lower().replace(' ', '_')}_ids"
    )
    
    if item_ids_text:
        # Parse item IDs
        item_ids = [id.strip() for id in item_ids_text.split("\n") if id.strip()]
        
        if item_ids:
            st.info(f"Found {len(item_ids)} {item_type} to process")
            return item_ids
        else:
            st.error(f"No valid {item_type} IDs provided")
    
    return None


def create_help_section(
    title: str,
    sections: Dict[str, str],
    expanded: bool = False
) -> None:
    """
    Create a consistent help section with multiple subsections.
    
    Args:
        title: Title for the help section
        sections: Dictionary of section titles and content
        expanded: Whether the help section should be expanded by default
    """
    with st.expander(title, expanded=expanded):
        for section_title, section_content in sections.items():
            st.markdown(f"### {section_title}")
            st.markdown(section_content)


def show_tool_header(
    title: str,
    description: str,
    icon: str = None
) -> None:
    """
    Show a consistent header for tools.
    
    Args:
        title: Title of the tool
        description: Description of what the tool does
        icon: Optional icon to display
    """
    if icon:
        st.title(f"{icon} {title}")
    else:
        st.title(title)
    
    st.markdown(f"""
    ## {title}
    
    {description}
    """)


def get_environment_setting(
    setting_name: str,
    default_value: Any = None,
    setting_type: type = str
) -> Any:
    """
    Get a setting from environment variables with type conversion.
    
    Args:
        setting_name: Name of the environment variable
        default_value: Default value if not found
        setting_type: Type to convert the value to
        
    Returns:
        The setting value with proper type conversion
    """
    env_value = os.environ.get(setting_name)
    
    if env_value is None:
        return default_value
    
    try:
        if setting_type == bool:
            return env_value.lower() in ("true", "1", "yes", "on")
        elif setting_type == int:
            return int(env_value)
        elif setting_type == float:
            return float(env_value)
        else:
            return setting_type(env_value)
    except (ValueError, TypeError):
        logger.warning(f"Could not convert environment variable {setting_name}={env_value} to {setting_type.__name__}, using default")
        return default_value


def initialize_session_state(defaults: Dict[str, Any]) -> None:
    """
    Initialize session state with default values.
    
    Args:
        defaults: Dictionary of default values for session state
    """
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_session_cache(prefix: str = None) -> None:
    """
    Clear cached values from session state.
    
    Args:
        prefix: Optional prefix to filter which keys to clear
    """
    keys_to_remove = []
    
    for key in st.session_state.keys():
        if prefix is None or key.startswith(prefix):
            if key not in ["authenticated", "gis", "username", "debug_mode"]:
                keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del st.session_state[key]
    
    if keys_to_remove:
        logger.info(f"Cleared {len(keys_to_remove)} cached values from session state")
