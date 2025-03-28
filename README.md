# SWCA GIS Tools

A collection of Python utilities designed to automate and streamline GIS workflows for SWCA Environmental Consultants. These tools interact with ArcGIS Online/Portal to perform operations that would otherwise require manual intervention through the web interface.

## Overview

SWCA GIS Tools provides programmatic access to ArcGIS Online/Portal resources, enabling automation of repetitive GIS tasks, batch processing of web maps and layers, and consistent application of filters and configurations.

### Current Capabilities

- **Web Map Filter Updates**: Programmatically update definition expressions (filters) in ArcGIS web maps
- **Recursive Layer Processing**: Process nested group layers within web maps
- **Field-Based Targeting**: Identify and update layers containing specific fields
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
     export ARCGIS_USERNAME=your_username
     export ARCGIS_PASSWORD=your_password
     export ARCGIS_PROFILE=your_profile
     ```
   - Alternatively, update the credentials in the script (not recommended for production)

## Usage

### Web Map Filter Utility

The `patch_webmap_filters.py` utility allows you to update definition expressions in web maps based on a target field.

#### Basic Usage

```python
from src.patch_webmap_filters import update_webmap_definition_by_field

# Set DEBUG_MODE = False in the script for production use

# Update all layers containing "project_number" field with a new filter
webmap_item_id = "3d7ba61233c744b997c9e275e8475254"
target_field = "project_number"
new_filter = "project_number = '123456'"

updated_layers = update_webmap_definition_by_field(webmap_item_id, target_field, new_filter)

if updated_layers:
    print(f"Successfully updated {len(updated_layers)} layers")
else:
    print("No layers were updated")
```

#### Command Line Execution

```bash
python src/patch_webmap_filters.py
```

This will run the script with the default parameters defined in the `__main__` block.

## Features

### Web Map Filter Updates

- **Problem**: When project parameters change, multiple web maps need to be updated with new filters
- **Solution**: `patch_webmap_filters.py` allows for programmatic updates to definition expressions across multiple layers in web maps
- **Benefit**: Ensures consistent filtering across all relevant layers without manual intervention

### Recursive Layer Processing

The tools can process complex web map structures, including:
- Group layers
- Nested layers
- Multiple operational layers

### Debug Mode

All tools support a debug mode that simulates operations without making actual changes to ArcGIS resources. This is useful for testing and validation.

```python
# Set to True for testing (no changes saved)
# Set to False for production (changes saved to server)
DEBUG_MODE = True
```

## Project Status

This project is in active development. Current status:

- ✅ Authentication with ArcGIS Online/Portal
- ✅ Retrieving web maps by item ID
- ✅ Parsing web map JSON structure
- ✅ Identifying layers that contain specific fields
- ✅ Recursive processing of nested group layers
- ✅ Updating definition expressions in web map JSON
- ✅ Debug mode for testing without making actual changes
- ✅ Basic error handling for layer processing

### Planned Improvements

- Command-line interface for script parameters
- Secure credential management
- Structured logging system
- Enhanced error handling and recovery
- Unit tests for core functions
- Support for batch processing multiple web maps
- Configuration system for environment-specific settings

## Security Considerations

The current implementation includes several security considerations:

1. **Credentials**: By default, the script looks for credentials in environment variables:
   - `ARCGIS_USERNAME`
   - `ARCGIS_PASSWORD`
   - `ARCGIS_PROFILE`

2. **Debug Mode**: The global `DEBUG_MODE` flag (default: `False`) controls whether changes are actually saved to the server.

3. **Error Handling**: The script includes error handling to prevent unintended operations.

## Contributing

Contributions to SWCA GIS Tools are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature-name`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature-name`)
5. Create a new Pull Request

## License

[Specify license information here]

## Contact

[Specify contact information here]
