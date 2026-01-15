# Clay GIS Tools

A Python-based web application and utility suite for automating GIS workflows in ArcGIS Online/Portal. Streamline operations that typically require manual intervention through the web interface.

![image](https://github.com/user-attachments/assets/b771d473-1635-4905-83ec-ea4d07bfec65)

## Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Development](#development)
- [Security](#security)
- [Contributing](#contributing)

## Features

### Core Capabilities

- **Web Map Filter Updates**: Programmatically update definition expressions (filters) across multiple layers in web maps
- **Web Map Form Configuration**: Update form elements and propagate configurations between layers
- **Web Map Analysis**: Analyze web map structure and generate detailed reports
- **Clip by Template Tag**: Automated clipping operations based on template tags
- **Recursive Layer Processing**: Handle complex web map structures including nested group layers
- **Batch Processing**: Process multiple web maps with the same configuration
- **Web Application Interface**: User-friendly Streamlit interface for non-technical users
- **Debug Mode**: Simulate operations without making actual changes

### Web Application Pages

- **Authentication**: Connect to ArcGIS Online/Portal
- **Web Map Filters**: Update definition expressions in web maps
- **Web Map Forms**: Configure form elements in web maps
- **Web Map Analysis**: Analyze and report on web map structures
- **Clip by Template Tag**: Perform clipping operations
- **Settings**: Configure application settings and debug mode

## Installation

### Prerequisites

- Python 3.8 or higher
- ArcGIS Online/Portal account with appropriate permissions
- Docker (optional, for containerized deployment)

### Quick Start

#### Option 1: Docker Compose (Recommended)

```bash
git clone https://github.com/swca/clay-gis-tools.git
cd clay-gis-tools
docker-compose up --build
```

Access the application at http://localhost:8501

#### Option 2: Docker (Manual)

```bash
git clone https://github.com/swca/clay-gis-tools.git
cd clay-gis-tools
docker build -t clay-gis-tools .
docker run -p 8501:8501 clay-gis-tools
```

#### Option 3: Local Installation

```bash
git clone https://github.com/swca/clay-gis-tools.git
cd clay-gis-tools
pip install -r requirements.txt
python app.py
```

## Configuration

### Environment Variables

Set the following environment variables for authentication:

**Windows (PowerShell):**
```powershell
$env:ARCGIS_USERNAME="your_username"
$env:ARCGIS_PASSWORD="your_password"
$env:ARCGIS_PROFILE="your_profile"
$env:DEBUG_MODE="True"  # Optional: Enable debug mode by default
```

**macOS/Linux:**
```bash
export ARCGIS_USERNAME=your_username
export ARCGIS_PASSWORD=your_password
export ARCGIS_PROFILE=your_profile
export DEBUG_MODE=True  # Optional: Enable debug mode by default
```

**Using .env file:**
Create a `.env` file in the project root:
```
ARCGIS_USERNAME=your_username
ARCGIS_PASSWORD=your_password
ARCGIS_PROFILE=your_profile
DEBUG_MODE=True
```

> **Note**: Credentials can also be entered directly in the web application interface. The application will attempt automatic authentication from environment variables on startup.

## Usage

### Web Application

1. Start the application:
   ```bash
   python app.py
   ```

2. Open your browser to http://localhost:8501

3. Navigate using the sidebar to access different tools:
   - Authenticate with ArcGIS Online/Portal
   - Use the various tools to perform operations
   - Configure settings including debug mode

### Command Line Utilities

#### Web Map Filter Updates

Update definition expressions in web maps based on target fields:

```bash
# Basic usage
python src/patch_webmap_filters.py

# With custom parameters
python src/patch_webmap_filters.py \
  --webmap_id "3d7ba61233c744b997c9e275e8475254" \
  --field "project_number" \
  --filter "project_number = '123456'" \
  --debug
```

#### Web Map Form Configuration

Update form configurations in web maps:

```bash
# Update a field in forms
python src/patch_webmap_forms.py update \
  "3d7ba61233c744b997c9e275e8475254" \
  --field "project_number" \
  --expression "expr/set-project-number" \
  --group "Metadata" \
  --debug

# Propagate form elements from one layer to others
python src/patch_webmap_forms.py propagate \
  "3d7ba61233c744b997c9e275e8475254" \
  --source "Source Layer Name" \
  --targets "Target Layer 1,Target Layer 2" \
  --fields "field1,field2" \
  --debug
```

### Python API

Use the tools programmatically in your own scripts:

```python
from src.patch_webmap_filters import update_webmap_definition_by_field
from src.patch_webmap_forms import update_webmap_forms, propagate_form_elements

# Update filters
webmap_item_id = "3d7ba61233c744b997c9e275e8475254"
updated_layers = update_webmap_definition_by_field(
    webmap_item_id,
    target_field="project_number",
    new_filter="project_number = '123456'"
)

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

## Development

### Project Structure

```
clay-gis-tools/
├── app.py                 # Streamlit application entry point
├── modules/               # Core application modules
│   ├── authentication.py  # ArcGIS authentication
│   ├── webmap_filters.py  # Filter update functionality
│   ├── webmap_forms.py    # Form configuration
│   ├── webmap_analysis.py # Analysis and reporting
│   └── ...
├── src/                   # Command-line utilities
│   ├── patch_webmap_filters.py
│   ├── patch_webmap_forms.py
│   └── ...
├── static/                # Static assets
└── requirements.txt       # Python dependencies
```

### Debug Mode

Debug mode allows you to test operations without making actual changes to ArcGIS resources:

- **Web Application**: Toggle debug mode in the Settings page
- **Command Line**: Use the `--debug` flag
- **Environment**: Set `DEBUG_MODE=True` in environment variables

When debug mode is enabled, operations are simulated and logged but not saved to the server.

### Testing maps

- `eb50014bde1b461aae56068ebee86eea`


### Development Guidelines

- Follow PEP 8 style guidelines
- Include type hints for function parameters and return values
- Add docstrings for all functions and classes
- Write unit tests for new functionality
- Update documentation to reflect changes

## Security

### Credential Management

- **Environment Variables**: Preferred method for production deployments
- **Session-based**: Web application uses session-based authentication with timeout
- **No Storage**: Credentials entered in the web interface are not persisted

### Safety Features

- **Debug Mode**: Default enabled to prevent accidental changes
- **Error Handling**: Comprehensive error handling prevents unintended operations
- **Logging**: Detailed logging of all operations for audit trails
- **Verification**: Changes are verified before committing to the server

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature-name`)
3. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin feature/your-feature-name`)
5. Create a new Pull Request

### Development Setup

1. Clone your fork:
   ```bash
   git clone https://github.com/your-username/clay-gis-tools.git
   cd clay-gis-tools
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables (see [Configuration](#configuration))

5. Run the application:
   ```bash
   python app.py
   ```

## License

[Add license information if applicable]

## Support

For issues, questions, or contributions, please use the GitHub issue tracker.
