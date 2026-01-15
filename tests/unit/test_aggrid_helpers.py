"""
Unit tests for AgGrid helper functions.

Tests the utility functions in frontend/components/aggrid_helpers.py
for creating and configuring AgGrid tables.
"""

import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class TestBuildColumnConfig(unittest.TestCase):
    """Test cases for _build_column_config function."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Import the module under test
        from frontend.components.aggrid_helpers import _build_column_config
        self.build_column_config = _build_column_config
    
    def test_checkbox_column_config(self):
        """Test checkbox column configuration."""
        config = {
            'type': 'checkbox',
            'editable': True,
            'header_name': 'Apply'
        }
        
        result = self.build_column_config('Apply', config)
        
        self.assertEqual(result['cellRenderer'], 'agCheckboxCellRenderer')
        self.assertEqual(result['cellEditor'], 'agCheckboxCellEditor')
        self.assertTrue(result['editable'])
        self.assertEqual(result['headerName'], 'Apply')
    
    def test_selectbox_column_config(self):
        """Test selectbox column configuration."""
        config = {
            'type': 'selectbox',
            'options': ['Option 1', 'Option 2', 'Option 3'],
            'editable': True
        }
        
        result = self.build_column_config('Category', config)
        
        self.assertEqual(result['cellEditor'], 'agSelectCellEditor')
        self.assertEqual(result['cellEditorParams'], {'values': ['Option 1', 'Option 2', 'Option 3']})
        self.assertTrue(result['editable'])
    
    def test_text_column_config(self):
        """Test text column configuration."""
        config = {
            'type': 'text',
            'editable': True,
            'header_name': 'Name'
        }
        
        result = self.build_column_config('Name', config)
        
        self.assertEqual(result['cellEditor'], 'agTextCellEditor')
        self.assertTrue(result['editable'])
        self.assertEqual(result['headerName'], 'Name')
    
    def test_number_column_config(self):
        """Test number column configuration."""
        config = {
            'type': 'number',
            'editable': True
        }
        
        result = self.build_column_config('Count', config)
        
        self.assertEqual(result['cellEditor'], 'agNumberCellEditor')
        self.assertIn('numericColumn', result['type'])
        self.assertTrue(result['editable'])
    
    def test_readonly_column_config(self):
        """Test read-only column configuration."""
        config = {
            'type': 'text',
            'editable': False
        }
        
        result = self.build_column_config('ReadOnly', config)
        
        self.assertFalse(result['editable'])
    
    def test_hidden_column_config(self):
        """Test hidden column configuration."""
        config = {
            'type': 'text',
            'hide': True
        }
        
        result = self.build_column_config('_internal', config)
        
        self.assertTrue(result['hide'])
    
    def test_width_config(self):
        """Test column width configuration."""
        config = {
            'type': 'text',
            'width': 200
        }
        
        result = self.build_column_config('WideColumn', config)
        
        self.assertEqual(result['width'], 200)
    
    def test_pinned_column_config(self):
        """Test pinned column configuration."""
        config = {
            'type': 'text',
            'pinned': 'left'
        }
        
        result = self.build_column_config('PinnedColumn', config)
        
        self.assertEqual(result['pinned'], 'left')
    
    def test_default_editable(self):
        """Test default editable is True when not specified."""
        config = {'type': 'text'}
        
        result = self.build_column_config('DefaultEditable', config)
        
        self.assertTrue(result['editable'])


class TestBuildCellStyleJs(unittest.TestCase):
    """Test cases for _build_cell_style_js function."""
    
    def setUp(self):
        """Set up test fixtures."""
        from frontend.components.aggrid_helpers import _build_cell_style_js
        self.build_cell_style_js = _build_cell_style_js
    
    def test_single_condition_style(self):
        """Test single condition styling."""
        style_config = {
            'conditions': [
                {'condition': '> 0', 'background': '#ffcccc', 'color': '#cc0000'}
            ]
        }
        
        result = self.build_cell_style_js(style_config)
        
        self.assertIsNotNone(result)
        # The result should be a JsCode object
        self.assertTrue(hasattr(result, 'js_code'))
    
    def test_multiple_conditions_style(self):
        """Test multiple conditions styling."""
        style_config = {
            'conditions': [
                {'condition': '> 10', 'background': '#ff0000'},
                {'condition': '> 5', 'background': '#ffff00'}
            ]
        }
        
        result = self.build_cell_style_js(style_config)
        
        self.assertIsNotNone(result)
    
    def test_empty_conditions(self):
        """Test empty conditions returns None."""
        style_config = {'conditions': []}
        
        result = self.build_cell_style_js(style_config)
        
        self.assertIsNone(result)
    
    def test_no_conditions_key(self):
        """Test missing conditions key returns None."""
        style_config = {}
        
        result = self.build_cell_style_js(style_config)
        
        self.assertIsNone(result)


class TestGetSeverityStyleConfig(unittest.TestCase):
    """Test cases for get_severity_style_config function."""
    
    def setUp(self):
        """Set up test fixtures."""
        from frontend.components.aggrid_helpers import get_severity_style_config
        self.get_severity_style_config = get_severity_style_config
    
    def test_returns_all_severity_columns(self):
        """Test that all severity columns are configured."""
        result = self.get_severity_style_config()
        
        self.assertIn('Critical', result)
        self.assertIn('Warnings', result)
        self.assertIn('Info', result)
    
    def test_critical_style_config(self):
        """Test Critical column style configuration."""
        result = self.get_severity_style_config()
        
        critical_config = result['Critical']
        self.assertIn('conditions', critical_config)
        self.assertEqual(len(critical_config['conditions']), 1)
        self.assertEqual(critical_config['conditions'][0]['condition'], '> 0')
        self.assertIn('background', critical_config['conditions'][0])
    
    def test_warnings_style_config(self):
        """Test Warnings column style configuration."""
        result = self.get_severity_style_config()
        
        warnings_config = result['Warnings']
        self.assertIn('conditions', warnings_config)
        self.assertEqual(warnings_config['conditions'][0]['condition'], '> 0')
    
    def test_info_style_config(self):
        """Test Info column style configuration."""
        result = self.get_severity_style_config()
        
        info_config = result['Info']
        self.assertIn('conditions', info_config)
        self.assertEqual(info_config['conditions'][0]['condition'], '> 0')


class TestMapStreamlitColumnConfig(unittest.TestCase):
    """Test cases for map_streamlit_column_config function."""
    
    def setUp(self):
        """Set up test fixtures."""
        from frontend.components.aggrid_helpers import map_streamlit_column_config
        self.map_streamlit_column_config = map_streamlit_column_config
    
    def test_unknown_config_type(self):
        """Test handling of unknown config type."""
        # Use a mock object with no specific type indicators
        mock_config = MagicMock()
        mock_config.__class__.__name__ = 'UnknownColumn'
        
        result = self.map_streamlit_column_config(mock_config, 'test_column')
        
        self.assertEqual(result.get('type'), 'text')
    
    def test_checkbox_detection(self):
        """Test detection of checkbox column type."""
        mock_config = MagicMock()
        mock_config.__class__.__name__ = 'CheckboxColumn'
        
        result = self.map_streamlit_column_config(mock_config, 'test_column')
        
        self.assertEqual(result.get('type'), 'checkbox')
    
    def test_selectbox_detection(self):
        """Test detection of selectbox column type."""
        mock_config = MagicMock()
        mock_config.__class__.__name__ = 'SelectboxColumn'
        mock_config.options = ['A', 'B', 'C']
        
        result = self.map_streamlit_column_config(mock_config, 'test_column')
        
        self.assertEqual(result.get('type'), 'selectbox')
        self.assertEqual(result.get('options'), ['A', 'B', 'C'])
    
    def test_number_detection(self):
        """Test detection of number column type."""
        mock_config = MagicMock()
        mock_config.__class__.__name__ = 'NumberColumn'
        
        result = self.map_streamlit_column_config(mock_config, 'test_column')
        
        self.assertEqual(result.get('type'), 'number')


class TestCreateEditableGridMocked(unittest.TestCase):
    """Test cases for create_editable_grid function with mocked AgGrid."""
    
    @patch('frontend.components.aggrid_helpers.AgGrid')
    @patch('frontend.components.aggrid_helpers.GridOptionsBuilder')
    def test_create_editable_grid_calls_aggrid(self, mock_gob, mock_aggrid):
        """Test that create_editable_grid calls AgGrid correctly."""
        from frontend.components.aggrid_helpers import create_editable_grid
        
        # Set up mocks
        mock_builder = MagicMock()
        mock_gob.from_dataframe.return_value = mock_builder
        mock_builder.build.return_value = {'columnDefs': []}
        mock_aggrid.return_value = {'data': pd.DataFrame(), 'selected_rows': []}
        
        # Create test data
        df = pd.DataFrame({'A': [1, 2, 3], 'B': ['a', 'b', 'c']})
        column_configs = {
            'A': {'type': 'number', 'editable': True},
            'B': {'type': 'text', 'editable': False}
        }
        
        # Call the function
        result = create_editable_grid(df, column_configs, key='test_grid')
        
        # Verify AgGrid was called
        mock_aggrid.assert_called_once()
        
        # Verify GridOptionsBuilder was used
        mock_gob.from_dataframe.assert_called_once()
    
    @patch('frontend.components.aggrid_helpers.AgGrid')
    @patch('frontend.components.aggrid_helpers.GridOptionsBuilder')
    def test_hidden_columns_configured(self, mock_gob, mock_aggrid):
        """Test that columns starting with underscore are hidden."""
        from frontend.components.aggrid_helpers import create_editable_grid
        
        # Set up mocks
        mock_builder = MagicMock()
        mock_gob.from_dataframe.return_value = mock_builder
        mock_builder.build.return_value = {'columnDefs': []}
        mock_aggrid.return_value = {'data': pd.DataFrame(), 'selected_rows': []}
        
        # Create test data with hidden column
        df = pd.DataFrame({'visible': [1, 2], '_hidden': ['a', 'b']})
        column_configs = {}
        
        # Call the function
        create_editable_grid(df, column_configs, key='test_grid')
        
        # Verify configure_column was called with hide=True for _hidden
        calls = mock_builder.configure_column.call_args_list
        hidden_call = [c for c in calls if c[0][0] == '_hidden']
        self.assertTrue(len(hidden_call) > 0)
        self.assertTrue(hidden_call[0][1].get('hide', False))


class TestCreateReadonlyGridMocked(unittest.TestCase):
    """Test cases for create_readonly_grid function with mocked AgGrid."""
    
    @patch('frontend.components.aggrid_helpers.AgGrid')
    @patch('frontend.components.aggrid_helpers.GridOptionsBuilder')
    def test_create_readonly_grid_not_editable(self, mock_gob, mock_aggrid):
        """Test that create_readonly_grid sets columns as not editable."""
        from frontend.components.aggrid_helpers import create_readonly_grid
        
        # Set up mocks
        mock_builder = MagicMock()
        mock_gob.from_dataframe.return_value = mock_builder
        mock_builder.build.return_value = {'columnDefs': []}
        mock_aggrid.return_value = {'data': pd.DataFrame(), 'selected_rows': []}
        
        # Create test data
        df = pd.DataFrame({'A': [1, 2, 3]})
        
        # Call the function
        create_readonly_grid(df, key='test_readonly')
        
        # Verify configure_default_column was called with editable=False
        mock_builder.configure_default_column.assert_called()
        call_kwargs = mock_builder.configure_default_column.call_args[1]
        self.assertFalse(call_kwargs.get('editable', True))
    
    @patch('frontend.components.aggrid_helpers.AgGrid')
    @patch('frontend.components.aggrid_helpers.GridOptionsBuilder')
    def test_selection_enabled(self, mock_gob, mock_aggrid):
        """Test that selection can be enabled."""
        from frontend.components.aggrid_helpers import create_readonly_grid
        
        # Set up mocks
        mock_builder = MagicMock()
        mock_gob.from_dataframe.return_value = mock_builder
        mock_builder.build.return_value = {'columnDefs': []}
        mock_aggrid.return_value = {'data': pd.DataFrame(), 'selected_rows': []}
        
        # Create test data
        df = pd.DataFrame({'A': [1, 2, 3]})
        
        # Call the function with selection enabled
        create_readonly_grid(df, key='test_selection', enable_selection=True)
        
        # Verify configure_selection was called
        mock_builder.configure_selection.assert_called_once()


if __name__ == "__main__":
    unittest.main()
