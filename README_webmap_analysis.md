# Web Map Analysis Tool

## Overview

The Web Map Analysis tool is a comprehensive utility for analyzing ArcGIS Online web maps to identify optimization opportunities and ensure best practices are followed. It performs various checks on layers, tables, and configurations to help improve performance and user experience.

## Features

### Layer Optimization Checks
- **Record Count Report**: Reports the number of records in all queryable layers
- **Layer Age Analysis**: Identifies layers created more than 2 years ago
- **Reserved Keyword Detection**: Checks for field names using SQL or ArcGIS reserved words
- **Layer Count Analysis**: Warns when web maps exceed recommended layer thresholds

### Performance Checks
- **Drawing Optimization**: Verifies if optimized layer drawing is enabled
- **Query Capabilities**: Ensures layers support queries for field app compatibility
- **Visibility Ranges**: Checks if appropriate scale dependencies are set

### Configuration Analysis
- **Popup Configuration**: Evaluates popup settings and field visibility
- **Editable Layers**: Identifies layers that may need edit capabilities

### Field Analysis
- **Meaningful Aliases**: Checks if fields have user-friendly aliases
- **Field Structure**: Analyzes field naming conventions and suggests improvements

## Usage

### Streamlit Interface

1. Navigate to the "Web Map Analysis" page in the application
2. Select a web map by:
   - Entering a Web Map Item ID directly, or
   - Searching for web maps by title, tags, or description
3. Configure analysis options:
   - Select which categories to analyze
   - Set thresholds for warnings
4. Click "Analyze Web Map" to run the analysis
5. View results in multiple formats:
   - Summary view with performance score
   - Detailed layer analysis
   - Issues by category
   - Interactive visualizations
   - Export options (Text, CSV, JSON)

### Programmatic Usage

```python
from arcgis.gis import GIS
from analyze_webmap import WebMapAnalyzer, analyze_webmap
from analysis_reports import create_report

# Connect to ArcGIS
gis = GIS(username="your_username", password="your_password")

# Analyze a web map
webmap_id = "your_webmap_id"
results = analyze_webmap(gis, webmap_id, debug_mode=True)

# Generate reports
report_gen = create_report(results)
text_report = report_gen.generate_summary_report()
csv_report = report_gen.generate_detailed_csv()
json_export = report_gen.generate_json_export()

# Check performance score
score_info = report_gen.format_performance_score()
print(f"Performance: {score_info['grade']} - {score_info['status']}")
```

## Performance Scoring

The tool calculates a performance score (0-100) based on:
- Number and severity of issues found
- Total layer/table count
- Critical issues have the highest impact

### Score Grades
- **A (90-100)**: Excellent - Web map is well-optimized
- **B (80-89)**: Good - Minor improvements recommended
- **C (70-79)**: Fair - Several optimizations needed
- **D (60-69)**: Poor - Significant issues to address
- **F (0-59)**: Critical - Major optimization required

## Analysis Categories

### 1. Record Counts
- Reports the number of records in each layer/table
- Identifies performance impact levels:
  - Low: < 5,000 records
  - Medium: 5,000 - 10,000 records
  - High: > 10,000 records

### 2. Layer Age
- Checks creation date of layers
- Flags layers older than 2 years for review
- Helps identify potentially outdated content

### 3. Reserved Keywords
- Comprehensive list of SQL and ArcGIS reserved words
- Prevents potential conflicts in queries and applications
- Includes common problematic field names

### 4. Field Aliases
- Checks for missing or non-meaningful aliases
- Suggests improvements for cryptic field names
- Patterns recognized:
  - `fld_` → "Field"
  - `dt_` → "Date"
  - `num_` → "Number"
  - And many more...

### 5. Drawing Optimization
- Checks for advanced query capabilities
- Verifies statistics support
- Identifies tile caching status

### 6. Query Capabilities
- Critical for Field Maps and other applications
- Ensures layers support attribute queries
- Flags non-queryable layers

### 7. Visibility Ranges
- Checks min/max scale dependencies
- Identifies overly broad visibility ranges
- Recommends scale limits for performance

### 8. Popup Configuration
- Verifies popups are configured
- Checks for popup titles
- Warns about too many visible fields (>15)

## Export Options

### Text Report
- Human-readable summary
- Includes all findings and recommendations
- Suitable for documentation and sharing

### CSV Report
- Detailed issue breakdown
- One row per issue
- Includes severity, recommendations
- Easy to filter and sort in Excel

### JSON Export
- Complete analysis results
- Structured data format
- Suitable for further processing
- Can be imported into other tools

## Best Practices

1. **Keep layer counts reasonable** - Aim for 15 or fewer layers per web map
2. **Use meaningful field aliases** - Help users understand data
3. **Enable query capabilities** - Required for Field Maps and other apps
4. **Set visibility ranges** - Improve performance at different scales
5. **Configure popups** - Enhance user experience with relevant information
6. **Review old layers** - Keep content current and relevant
7. **Avoid reserved keywords** - Prevent potential conflicts

## Configuration

### Thresholds (Adjustable in UI)
- Layer Count Warning: Default 15 layers
- Record Count Warning: Default 10,000 records
- Layer Age: Fixed at 2 years

### Debug Mode
- Set via Settings page or session state
- When enabled, performs read-only analysis
- No changes are made to web maps

## Troubleshooting

### Common Issues
- **Analysis fails**: Check that you have access to the web map and all its layers
- **No results**: Ensure the web map contains operational layers
- **Performance issues**: Large web maps may take longer to analyze
- **Missing layer info**: Some layers may not expose all metadata

### Error Handling
- Graceful handling of inaccessible layers
- Continues analysis even if some checks fail
- Detailed logging for debugging

## File Structure

```
src/
├── analyze_webmap.py       # Core analysis logic
├── analysis_reports.py     # Report generation
└── test_analyze_webmap.py  # Test script

modules/
└── webmap_analysis.py      # Streamlit UI
```

## Dependencies

- arcgis>=2.0.0
- pandas>=2.0.0
- plotly>=5.0.0
- streamlit>=1.30.0

## Future Enhancements

1. **Symbology Analysis**: Check for complex rendering that impacts performance
2. **Attachment Analysis**: Identify layers with large attachments
3. **Label Analysis**: Check for overlapping or complex labeling
4. **Relationship Analysis**: Identify related tables and their impact
5. **Service Type Analysis**: Differentiate between hosted and referenced services
6. **Offline Compatibility**: Check for offline-enabled layers
7. **Time-Enabled Analysis**: Identify time-aware layers and their configuration
