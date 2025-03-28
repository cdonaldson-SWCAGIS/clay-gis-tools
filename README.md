# Clay GIS Tools

A collection of Python utilities and a web application designed to automate and streamline GIS workflows for AGOL Admins. These tools interact with ArcGIS Online/Portal to perform operations that would otherwise require manual intervention through the web interface.

![image](https://github.com/user-attachments/assets/b771d473-1635-4905-83ec-ea4d07bfec65)


### Current Capabilities

- **Web Map Filter Updates**: Programmatically update definition expressions (filters) in ArcGIS web maps
- **Web Map Form Configuration**: Update form elements and propagate form configurations between layers
- **Recursive Layer Processing**: Process nested group layers within web maps
- **Field-Based Targeting**: Identify and update layers containing specific fields
- **Batch Processing**: Process multiple web maps with the same configuration
- **Web Application Interface**: User-friendly Streamlit interface for non-technical users
- **Debug/Test Mode**: Simulate operations without making actual changes

## Installation

### Prerequisites

- Python 3.x
- ArcGIS Online/Portal account with appropriate permissions

### Setup

1. Clone this repository:
   ```
   git clone https://github.com/swca/swca-gis-tools.git
   cd swca-gis-tools
   ```

2. Install required packages:
   ```
   pip install -r requirements.txt
   ```

3. Configure authentication:
   - Set environment variables for ArcGIS credentials:
     ```
     # For Windows
     set ARCGIS_USERNAME=your_username
     set ARCGIS_PASSWORD=your_password
     set ARCGIS_PROFILE=your_profile
     
     # For macOS/Linux
     export ARCGIS_USERNAME=your_username
     export ARCGIS_PASSWORD=your_password
     export ARCGIS_PROFILE=your_profile
     ```
   - Alternatively, you can enter credentials directly in the web application or update them in the script (not recommended for production)

## Usage

### Web Application

The Streamlit web application provides a user-friendly interface for accessing all tools:

1. Start the web application:
   ```
   python app.py
   ```

2. Open your browser and navigate to the URL displayed in the terminal (typically http://localhost:8501)

3. Use the navigation sidebar to access different tools:
   - **Authentication**: Connect to ArcGIS Online/Portal
   - **Web Map Filters**: Update definition expressions in web maps
   - **Web Map Forms**: Configure form elements in web maps
   - **Settings**: Configure application settings

### Command Line Utilities

#### Web Map Filter Utility

The `patch_webmap_filters.py` utility allows you to update definition expressions in web maps based on a target field.

```bash
# Basic usage
python src/patch_webmap_filters.py

# With custom parameters
python src/patch_webmap_filters.py --webmap_id "3d7ba61233c744b997c9e275e8475254" --field "project_number" --filter "project_number = '123456'" --debug
```

#### Web Map Forms Utility

The `patch_webmap_forms.py` utility allows you to update form configurations in web maps.

```bash
# Update a field in forms
python src/patch_webmap_forms.py update "3d7ba61233c744b997c9e275e8475254" --field "project_number" --expression "expr/set-project-number" --group "Metadata" --debug

# Propagate form elements from one layer to others
python src/patch_webmap_forms.py propagate "3d7ba61233c744b997c9e275e8475254" --source "Source Layer Name" --targets "Target Layer 1,Target Layer 2" --fields "field1,field2" --debug
```

#### Python API Usage

```python
from src.patch_webmap_filters import update_webmap_definition_by_field
from src.patch_webmap_forms import update_webmap_forms, propagate_form_elements

# Update filters
webmap_item_id = "3d7ba61233c744b997c9e275e8475254"
target_field = "project_number"
new_filter = "project_number = '123456'"

updated_layers = update_webmap_definition_by_field(webmap_item_id, target_field, new_filter)

if updated_layers:
    print(f"Successfully updated {len(updated_layers)} layers")
else:
    print("No layers were updated")

# Update forms
updated_layers = update_webmap_forms(
    webmap_item_id,
    field_name="project_number",
    expression_name="expr/set-project-number",
    group_name="Metadata"
)

# Propagate form elements
updated_layers = propagate_form_elements(
    webmap_item_id,
    source_layer_name="Source Layer Name",
    target_layer_names=["Target Layer 1", "Target Layer 2"],
    field_names=["field1", "field2"]
)
```

## Features

### Web Map Filter Updates

- **Problem**: When project parameters change, multiple web maps need to be updated with new filters
- **Solution**: The Web Map Filters tool allows for programmatic updates to definition expressions across multiple layers in web maps
- **Benefit**: Ensures consistent filtering across all relevant layers without manual intervention
- **Batch Processing**: Update multiple web maps with the same filter in a single operation

### Web Map Form Configuration

- **Problem**: Form configurations need to be consistent across multiple layers and web maps
- **Solution**: The Web Map Forms tool allows for adding/updating form elements and propagating configurations between layers
- **Benefit**: Ensures consistent form behavior and appearance across all layers
- **Capabilities**:
  - Add or update field elements in forms
  - Configure expressions for field values
  - Organize fields into logical groups
  - Copy form configurations from one layer to others

### Recursive Layer Processing

The tools can process complex web map structures, including:
- Group layers
- Nested layers
- Multiple operational layers

### Web Application Interface

The Streamlit web application provides:
- User-friendly interface for non-technical users
- Authentication with ArcGIS Online/Portal
- Search functionality for finding web maps
- Form-based configuration of tool parameters
- Real-time feedback on operations
- Detailed help information for each tool

### Debug Mode

All tools support a debug mode that simulates operations without making actual changes to ArcGIS resources. This is useful for testing and validation.

```python
# Set to True for testing (no changes saved)
# Set to False for production (changes saved to server)
DEBUG_MODE = True
```

The web application includes a global debug mode setting that can be toggled in the Settings page.

## Project Status

This project is in active development. Current status:

- ✅ Authentication with ArcGIS Online/Portal
- ✅ Retrieving web maps by item ID
- ✅ Parsing web map JSON structure
- ✅ Identifying layers that contain specific fields
- ✅ Recursive processing of nested group layers
- ✅ Updating definition expressions in web map JSON
- ✅ Updating form configurations in web map JSON
- ✅ Propagating form elements between layers
- ✅ Web application interface with Streamlit
- ✅ Debug mode for testing without making actual changes
- ✅ Basic error handling for layer processing
- ✅ Batch processing for multiple web maps
- ✅ Structured logging system

### Planned Improvements

- Enhanced command-line interface for script parameters
- Secure credential management
- Enhanced error handling and recovery
- Unit tests for core functions
- Configuration system for environment-specific settings
- Additional tools for other ArcGIS Online/Portal operations
- User authentication and role-based access control
- Scheduled task execution

## Security Considerations

The current implementation includes several security considerations:

1. **Credentials**: 
   - The application looks for credentials in environment variables:
     - `ARCGIS_USERNAME`
     - `ARCGIS_PASSWORD`
     - `ARCGIS_PROFILE`
   - The web application allows for manual entry of credentials without storing them
   - Session-based authentication with timeout settings

2. **Debug Mode**: 
   - The global `DEBUG_MODE` flag controls whether changes are actually saved to the server
   - The web application includes a global debug mode setting that can be toggled in the Settings page
   - Debug mode is enabled by default to prevent accidental changes

3. **Error Handling**: 
   - Comprehensive error handling to prevent unintended operations
   - Detailed logging of operations and errors
   - Verification of changes before committing to the server

## Contributing

Contributions to SWCA GIS Tools are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature-name`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature-name`)
5. Create a new Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Include type hints for function parameters and return values
- Add docstrings for all functions and classes
- Write unit tests for new functionality
- Update documentation to reflect changes

