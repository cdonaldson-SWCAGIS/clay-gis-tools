"""
AgGrid Helper Functions for Streamlit

Provides utility functions for creating and configuring AgGrid tables
to replace Streamlit's native st.data_editor and st.dataframe components.
"""

import pandas as pd
from typing import Dict, List, Any, Optional, Callable
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode, JsCode


def create_editable_grid(
    df: pd.DataFrame,
    column_configs: Dict[str, Dict[str, Any]],
    key: str,
    height: int = 400,
    fit_columns: bool = True,
    theme: str = "streamlit"
) -> Dict[str, Any]:
    """
    Create an editable AgGrid table with column configurations.
    
    Args:
        df: DataFrame to display
        column_configs: Dictionary mapping column names to their configurations
            Each config can have:
            - 'type': 'checkbox', 'selectbox', 'text', 'number'
            - 'editable': bool
            - 'options': list (for selectbox)
            - 'header_name': str (display name)
            - 'width': int
            - 'hide': bool
        key: Unique key for the grid
        height: Grid height in pixels
        fit_columns: Whether to fit columns to grid width
        theme: Grid theme ('streamlit', 'alpine', 'balham', etc.)
    
    Returns:
        Grid response dictionary with 'data' and 'selected_rows' keys
    """
    gb = GridOptionsBuilder.from_dataframe(df)
    
    # Configure default column properties
    gb.configure_default_column(
        resizable=True,
        sortable=True,
        filter=True
    )
    
    # Apply column-specific configurations
    for col_name, config in column_configs.items():
        if col_name not in df.columns:
            continue
            
        col_config = _build_column_config(col_name, config)
        gb.configure_column(col_name, **col_config)
    
    # Hide columns starting with underscore
    for col in df.columns:
        if col.startswith('_'):
            gb.configure_column(col, hide=True)
    
    grid_options = gb.build()
    
    # Return the grid
    return AgGrid(
        df,
        gridOptions=grid_options,
        height=height,
        fit_columns_on_grid_load=fit_columns,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        data_return_mode=DataReturnMode.AS_INPUT,
        theme=theme,
        key=key,
        allow_unsafe_jscode=True
    )


def create_readonly_grid(
    df: pd.DataFrame,
    column_configs: Optional[Dict[str, Dict[str, Any]]] = None,
    key: str = "readonly_grid",
    height: int = 400,
    fit_columns: bool = True,
    theme: str = "streamlit",
    enable_selection: bool = False,
    selection_mode: str = "single"
) -> Dict[str, Any]:
    """
    Create a read-only AgGrid table with sorting and filtering.
    
    Args:
        df: DataFrame to display
        column_configs: Optional dictionary mapping column names to configurations
        key: Unique key for the grid
        height: Grid height in pixels
        fit_columns: Whether to fit columns to grid width
        theme: Grid theme
        enable_selection: Whether to enable row selection
        selection_mode: 'single' or 'multiple'
    
    Returns:
        Grid response dictionary
    """
    gb = GridOptionsBuilder.from_dataframe(df)
    
    # Configure default column properties (read-only)
    gb.configure_default_column(
        resizable=True,
        sortable=True,
        filter=True,
        editable=False
    )
    
    # Apply column-specific configurations if provided
    if column_configs:
        for col_name, config in column_configs.items():
            if col_name not in df.columns:
                continue
            
            col_config = _build_column_config(col_name, config)
            col_config['editable'] = False  # Ensure read-only
            gb.configure_column(col_name, **col_config)
    
    # Configure selection if enabled
    if enable_selection:
        gb.configure_selection(
            selection_mode=selection_mode,
            use_checkbox=False
        )
    
    grid_options = gb.build()
    
    return AgGrid(
        df,
        gridOptions=grid_options,
        height=height,
        fit_columns_on_grid_load=fit_columns,
        update_mode=GridUpdateMode.SELECTION_CHANGED if enable_selection else GridUpdateMode.NO_UPDATE,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        theme=theme,
        key=key,
        allow_unsafe_jscode=True
    )


def create_styled_readonly_grid(
    df: pd.DataFrame,
    style_columns: Dict[str, Dict[str, Any]],
    key: str = "styled_grid",
    height: int = 400,
    fit_columns: bool = True,
    theme: str = "streamlit",
    enable_selection: bool = False
) -> Dict[str, Any]:
    """
    Create a read-only AgGrid with conditional cell styling.
    
    Args:
        df: DataFrame to display
        style_columns: Dictionary mapping column names to style configurations
            Each config should have:
            - 'conditions': list of dicts with 'condition', 'style' keys
              Example: [{'condition': '>0', 'background': '#ffcccc'}]
        key: Unique key for the grid
        height: Grid height in pixels
        fit_columns: Whether to fit columns to grid width
        theme: Grid theme
        enable_selection: Whether to enable row selection
    
    Returns:
        Grid response dictionary
    """
    gb = GridOptionsBuilder.from_dataframe(df)
    
    # Configure default column properties
    gb.configure_default_column(
        resizable=True,
        sortable=True,
        filter=True,
        editable=False
    )
    
    # Apply styling configurations
    for col_name, style_config in style_columns.items():
        if col_name not in df.columns:
            continue
        
        cell_style = _build_cell_style_js(style_config)
        gb.configure_column(
            col_name,
            cellStyle=cell_style
        )
    
    if enable_selection:
        gb.configure_selection(selection_mode="single", use_checkbox=False)
    
    grid_options = gb.build()
    
    return AgGrid(
        df,
        gridOptions=grid_options,
        height=height,
        fit_columns_on_grid_load=fit_columns,
        update_mode=GridUpdateMode.SELECTION_CHANGED if enable_selection else GridUpdateMode.NO_UPDATE,
        data_return_mode=DataReturnMode.FILTERED_AND_SORTED,
        theme=theme,
        key=key,
        allow_unsafe_jscode=True
    )


def _build_column_config(col_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build AgGrid column configuration from simplified config dict.
    
    Args:
        col_name: Column name
        config: Configuration dictionary
    
    Returns:
        AgGrid-compatible column configuration
    """
    col_config = {}
    
    # Header name
    if 'header_name' in config:
        col_config['headerName'] = config['header_name']
    
    # Width
    if 'width' in config:
        col_config['width'] = config['width']
    
    # Hide column
    if 'hide' in config:
        col_config['hide'] = config['hide']
    
    # Editable
    col_config['editable'] = config.get('editable', True)
    
    # Column type handling
    col_type = config.get('type', 'text')
    
    if col_type == 'checkbox':
        col_config['cellRenderer'] = 'agCheckboxCellRenderer'
        col_config['cellEditor'] = 'agCheckboxCellEditor'
        
    elif col_type == 'selectbox':
        options = config.get('options', [])
        col_config['cellEditor'] = 'agSelectCellEditor'
        col_config['cellEditorParams'] = {'values': options}
        
    elif col_type == 'number':
        col_config['type'] = ['numericColumn', 'numberColumnFilter']
        col_config['cellEditor'] = 'agNumberCellEditor'
        
    elif col_type == 'text':
        col_config['cellEditor'] = 'agTextCellEditor'
    
    # Pin column
    if 'pinned' in config:
        col_config['pinned'] = config['pinned']
    
    return col_config


def _build_cell_style_js(style_config: Dict[str, Any]) -> JsCode:
    """
    Build JavaScript cell style function for conditional styling.
    
    Args:
        style_config: Style configuration with conditions
    
    Returns:
        JsCode object for cellStyle
    """
    conditions = style_config.get('conditions', [])
    
    if not conditions:
        return None
    
    # Build JavaScript conditional styling
    js_conditions = []
    for cond in conditions:
        condition = cond.get('condition', '')
        background = cond.get('background', '')
        color = cond.get('color', '')
        
        style_parts = []
        if background:
            style_parts.append(f"backgroundColor: '{background}'")
        if color:
            style_parts.append(f"color: '{color}'")
        
        if style_parts and condition:
            js_conditions.append(
                f"if (params.value {condition}) {{ return {{{', '.join(style_parts)}}}; }}"
            )
    
    if not js_conditions:
        return None
    
    js_code = f"""
    function(params) {{
        {' '.join(js_conditions)}
        return null;
    }}
    """
    
    return JsCode(js_code)


def map_streamlit_column_config(
    st_config: Dict[str, Any],
    column_name: str
) -> Dict[str, Any]:
    """
    Map Streamlit column_config to AgGrid column configuration.
    
    Args:
        st_config: Streamlit column configuration (st.column_config.*)
        column_name: Name of the column
    
    Returns:
        AgGrid-compatible column configuration
    """
    ag_config = {}
    
    # Get the config type by checking the class name or structure
    config_type = type(st_config).__name__ if hasattr(st_config, '__class__') else 'unknown'
    
    # Common properties
    if hasattr(st_config, 'label'):
        ag_config['header_name'] = st_config.label
    if hasattr(st_config, 'help'):
        ag_config['headerTooltip'] = st_config.help
    if hasattr(st_config, 'disabled'):
        ag_config['editable'] = not st_config.disabled
    if hasattr(st_config, 'width'):
        ag_config['width'] = st_config.width
    
    # Type-specific handling
    if 'Checkbox' in config_type:
        ag_config['type'] = 'checkbox'
    elif 'Selectbox' in config_type:
        ag_config['type'] = 'selectbox'
        if hasattr(st_config, 'options'):
            ag_config['options'] = list(st_config.options)
    elif 'Number' in config_type:
        ag_config['type'] = 'number'
    else:
        ag_config['type'] = 'text'
    
    return ag_config


def get_severity_style_config() -> Dict[str, Dict[str, Any]]:
    """
    Get predefined style configuration for severity columns
    (Critical, Warnings, Info).
    
    Returns:
        Style configuration dictionary for use with create_styled_readonly_grid
    """
    return {
        'Critical': {
            'conditions': [
                {'condition': '> 0', 'background': '#ffcccc', 'color': '#cc0000'}
            ]
        },
        'Warnings': {
            'conditions': [
                {'condition': '> 0', 'background': '#ffffcc', 'color': '#cc9900'}
            ]
        },
        'Info': {
            'conditions': [
                {'condition': '> 0', 'background': '#ccffcc', 'color': '#009900'}
            ]
        }
    }
