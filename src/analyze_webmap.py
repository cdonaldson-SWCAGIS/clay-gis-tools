"""
Web Map Analysis Tool
Analyzes ArcGIS Online web maps for optimization opportunities and best practices.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple, Union
from collections import defaultdict

from arcgis.gis import GIS
from arcgis.features import FeatureLayer
from arcgis.mapping import Map

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("webmap_analysis")

# Reserved keywords that should be avoided in field names
RESERVED_KEYWORDS = {
    # SQL Reserved Words
    "SELECT", "FROM", "WHERE", "ORDER", "GROUP", "BY", "HAVING", "UNION",
    "INSERT", "UPDATE", "DELETE", "CREATE", "DROP", "ALTER", "TABLE",
    "INDEX", "VIEW", "JOIN", "LEFT", "RIGHT", "INNER", "OUTER", "ON",
    "AS", "AND", "OR", "NOT", "IN", "EXISTS", "BETWEEN", "LIKE", "IS",
    "NULL", "TRUE", "FALSE", "CASE", "WHEN", "THEN", "ELSE", "END",
    "DISTINCT", "COUNT", "SUM", "AVG", "MIN", "MAX", "ALL", "ANY",
    "LIMIT", "OFFSET", "FETCH", "FIRST", "LAST", "TOP", "PERCENT",
    
    # ArcGIS Reserved Fields
    "OBJECTID", "SHAPE", "SHAPE_LENGTH", "SHAPE_AREA", "GLOBALID",
    "CREATED_USER", "CREATED_DATE", "LAST_EDITED_USER", "LAST_EDITED_DATE",
    
    # Common Problematic Names
    "DATE", "TIME", "TIMESTAMP", "USER", "LEVEL", "SIZE", "TYPE",
    "STATUS", "STATE", "NAME", "VALUE", "KEY", "ID", "RANK"
}

# Common cryptic field names that should have aliases
CRYPTIC_FIELD_PATTERNS = {
    "fld_": "Field ",
    "col_": "Column ",
    "attr_": "Attribute ",
    "val_": "Value ",
    "num_": "Number ",
    "dt_": "Date ",
    "tm_": "Time ",
    "flg_": "Flag ",
    "ind_": "Indicator ",
    "cd_": "Code ",
    "desc_": "Description ",
    "nm_": "Name ",
    "addr_": "Address ",
    "st_": "State ",
    "cty_": "City ",
    "zip_": "ZIP Code ",
}


class WebMapAnalyzer:
    """Analyzes web maps for optimization opportunities and best practices."""
    
    def __init__(self, gis: GIS, debug_mode: bool = True):
        """
        Initialize the WebMapAnalyzer.
        
        Args:
            gis: Authenticated GIS object
            debug_mode: If True, doesn't make actual changes
        """
        self.gis = gis
        self.debug_mode = debug_mode
        self.analysis_results = {}
        
    def analyze_webmap(self, webmap_item_id: str) -> Dict[str, Any]:
        """
        Perform comprehensive analysis on a web map.
        
        Args:
            webmap_item_id: The item ID of the web map to analyze
            
        Returns:
            Dictionary containing analysis results
        """
        logger.info(f"Starting analysis of web map: {webmap_item_id}")
        
        # Initialize results structure
        self.analysis_results = {
            "webmap_info": {},
            "layer_optimization": {
                "record_counts": [],
                "old_layers": [],
                "reserved_keywords": [],
                "layer_count_analysis": {}
            },
            "performance_checks": {
                "drawing_optimization": [],
                "query_capabilities": [],
                "visibility_ranges": []
            },
            "configuration_analysis": {
                "popup_config": [],
                "editable_layers": []
            },
            "field_analysis": {
                "alias_issues": [],
                "field_structure": []
            },
            "recommendations": [],
            "summary": {
                "total_layers": 0,
                "total_tables": 0,
                "total_issues": 0,
                "critical_issues": 0
            }
        }
        
        try:
            # Get web map item
            webmap_item = self.gis.content.get(webmap_item_id)
            if not webmap_item:
                logger.error(f"Web map with ID {webmap_item_id} not found")
                return self.analysis_results
            
            # Store web map info
            self.analysis_results["webmap_info"] = {
                "title": webmap_item.title,
                "id": webmap_item.id,
                "owner": webmap_item.owner,
                "created": datetime.fromtimestamp(webmap_item.created / 1000).isoformat(),
                "modified": datetime.fromtimestamp(webmap_item.modified / 1000).isoformat(),
                "description": webmap_item.description or "No description",
                "tags": webmap_item.tags,
                "type": webmap_item.type
            }
            
            # Load web map
            webmap = Map(webmap_item)
            
            # Analyze layers and tables
            self._analyze_layers(webmap)
            
            # Generate recommendations
            self._generate_recommendations()
            
            # Calculate summary statistics
            self._calculate_summary()
            
            logger.info("Web map analysis completed successfully")
            
        except Exception as e:
            logger.error(f"Error analyzing web map: {str(e)}")
            self.analysis_results["error"] = str(e)
            
        return self.analysis_results
    
    def _analyze_layers(self, webmap: Map):
        """Analyze all layers and tables in the web map."""
        # Process operational layers
        if hasattr(webmap, 'layers'):
            for layer in webmap.layers:
                self._analyze_single_layer(layer, "layer")
                self.analysis_results["summary"]["total_layers"] += 1
        
        # Process tables
        if hasattr(webmap, 'tables'):
            for table in webmap.tables:
                self._analyze_single_layer(table, "table")
                self.analysis_results["summary"]["total_tables"] += 1
        
        # Check total layer count
        total_items = self.analysis_results["summary"]["total_layers"] + \
                      self.analysis_results["summary"]["total_tables"]
        
        if total_items > 15:
            self.analysis_results["layer_optimization"]["layer_count_analysis"] = {
                "count": total_items,
                "threshold": 15,
                "recommendation": f"Web map has {total_items} layers/tables. Consider consolidating similar data or removing unnecessary layers for better field performance.",
                "severity": "warning" if total_items <= 25 else "critical"
            }
    
    def _analyze_single_layer(self, layer: Any, layer_type: str = "layer"):
        """Analyze a single layer or table."""
        try:
            layer_info = {
                "title": layer.title if hasattr(layer, 'title') else "Unnamed",
                "type": layer_type,
                "url": layer.url if hasattr(layer, 'url') else None,
                "id": layer.id if hasattr(layer, 'id') else None
            }
            
            if not layer_info["url"]:
                return
            
            # Create feature layer object for detailed analysis
            feature_layer = FeatureLayer(layer_info["url"], gis=self.gis)
            
            # 1. Check record count
            self._check_record_count(feature_layer, layer_info)
            
            # 2. Check layer age
            self._check_layer_age(feature_layer, layer_info)
            
            # 3. Check for reserved keywords in field names
            self._check_reserved_keywords(feature_layer, layer_info)
            
            # 4. Check field aliases
            self._check_field_aliases(feature_layer, layer_info)
            
            # 5. Check drawing optimization
            self._check_drawing_optimization(feature_layer, layer_info)
            
            # 6. Check query capabilities
            self._check_query_capabilities(feature_layer, layer_info)
            
            # 7. Check editable status
            self._check_editable_status(feature_layer, layer_info, layer)
            
            # 8. Check visibility ranges
            self._check_visibility_ranges(layer, layer_info)
            
            # 9. Check popup configuration
            self._check_popup_configuration(layer, layer_info)
            
        except Exception as e:
            logger.error(f"Error analyzing layer {layer_info.get('title', 'Unknown')}: {str(e)}")
    
    def _check_record_count(self, feature_layer: FeatureLayer, layer_info: Dict):
        """Check and report the number of records in the layer."""
        try:
            # Get record count
            count_result = feature_layer.query(return_count_only=True)
            record_count = count_result
            
            self.analysis_results["layer_optimization"]["record_counts"].append({
                "layer": layer_info["title"],
                "count": record_count,
                "type": layer_info["type"],
                "performance_impact": "high" if record_count > 10000 else "medium" if record_count > 5000 else "low"
            })
            
            if record_count > 10000:
                self.analysis_results["recommendations"].append({
                    "category": "Performance",
                    "layer": layer_info["title"],
                    "issue": f"Layer has {record_count:,} records",
                    "recommendation": "Consider implementing scale-dependent rendering or creating summary layers for better performance",
                    "severity": "warning"
                })
                
        except Exception as e:
            logger.warning(f"Could not get record count for {layer_info['title']}: {str(e)}")
    
    def _check_layer_age(self, feature_layer: FeatureLayer, layer_info: Dict):
        """Check if the layer was created more than 2 years ago."""
        try:
            # Try to get creation date from service properties
            if hasattr(feature_layer, 'properties') and hasattr(feature_layer.properties, 'serviceItemId'):
                service_item = self.gis.content.get(feature_layer.properties.serviceItemId)
                if service_item and hasattr(service_item, 'created'):
                    created_date = datetime.fromtimestamp(service_item.created / 1000)
                    age_days = (datetime.now() - created_date).days
                    
                    if age_days > 730:  # More than 2 years
                        years_old = age_days / 365.25
                        self.analysis_results["layer_optimization"]["old_layers"].append({
                            "layer": layer_info["title"],
                            "created": created_date.isoformat(),
                            "age_years": round(years_old, 1),
                            "recommendation": "Review if this layer is still needed or if it should be updated"
                        })
                        
        except Exception as e:
            logger.debug(f"Could not check age for {layer_info['title']}: {str(e)}")
    
    def _check_reserved_keywords(self, feature_layer: FeatureLayer, layer_info: Dict):
        """Check for reserved keywords in field names."""
        try:
            if hasattr(feature_layer.properties, 'fields'):
                problematic_fields = []
                
                for field in feature_layer.properties.fields:
                    field_name = field.get('name', '').upper()
                    if field_name in RESERVED_KEYWORDS:
                        problematic_fields.append({
                            "field": field.get('name'),
                            "alias": field.get('alias', ''),
                            "type": field.get('type', '')
                        })
                
                if problematic_fields:
                    self.analysis_results["layer_optimization"]["reserved_keywords"].append({
                        "layer": layer_info["title"],
                        "fields": problematic_fields,
                        "recommendation": "Consider renaming these fields to avoid potential conflicts",
                        "severity": "warning"
                    })
                    
        except Exception as e:
            logger.debug(f"Could not check reserved keywords for {layer_info['title']}: {str(e)}")
    
    def _check_field_aliases(self, feature_layer: FeatureLayer, layer_info: Dict):
        """Check if fields have meaningful aliases."""
        try:
            if hasattr(feature_layer.properties, 'fields'):
                fields_needing_aliases = []
                
                for field in feature_layer.properties.fields:
                    field_name = field.get('name', '')
                    field_alias = field.get('alias', '')
                    
                    # Skip system fields
                    if field_name.upper() in ['OBJECTID', 'SHAPE', 'GLOBALID']:
                        continue
                    
                    # Check if alias is missing or same as field name
                    if not field_alias or field_alias == field_name:
                        fields_needing_aliases.append({
                            "field": field_name,
                            "current_alias": field_alias or "None",
                            "suggested": self._suggest_alias(field_name)
                        })
                    
                    # Check for cryptic field names
                    elif any(field_name.lower().startswith(pattern) for pattern in CRYPTIC_FIELD_PATTERNS):
                        fields_needing_aliases.append({
                            "field": field_name,
                            "current_alias": field_alias,
                            "suggested": self._suggest_alias(field_name)
                        })
                
                if fields_needing_aliases:
                    self.analysis_results["field_analysis"]["alias_issues"].append({
                        "layer": layer_info["title"],
                        "fields": fields_needing_aliases,
                        "recommendation": "Add meaningful aliases to improve field readability",
                        "severity": "info"
                    })
                    
        except Exception as e:
            logger.debug(f"Could not check aliases for {layer_info['title']}: {str(e)}")
    
    def _suggest_alias(self, field_name: str) -> str:
        """Suggest a meaningful alias for a field name."""
        # Check cryptic patterns
        for pattern, replacement in CRYPTIC_FIELD_PATTERNS.items():
            if field_name.lower().startswith(pattern):
                remainder = field_name[len(pattern):]
                return f"{replacement}{remainder.replace('_', ' ').title()}"
        
        # Convert underscores to spaces and title case
        suggested = field_name.replace('_', ' ').title()
        
        # Common abbreviations
        abbreviations = {
            "Num": "Number",
            "Desc": "Description",
            "Addr": "Address",
            "St": "Street",
            "Rd": "Road",
            "Blvd": "Boulevard",
            "Ave": "Avenue",
            "Dt": "Date",
            "Tm": "Time"
        }
        
        for abbr, full in abbreviations.items():
            suggested = suggested.replace(f" {abbr} ", f" {full} ")
            if suggested.endswith(f" {abbr}"):
                suggested = suggested[:-len(abbr)] + full
        
        return suggested
    
    def _check_drawing_optimization(self, feature_layer: FeatureLayer, layer_info: Dict):
        """Check if drawing optimization is enabled."""
        try:
            # Check for advanced query capabilities which indicate optimization
            if hasattr(feature_layer.properties, 'advancedQueryCapabilities'):
                adv_query = feature_layer.properties.advancedQueryCapabilities
                
                # Check for optimization indicators
                has_optimization = (
                    adv_query.get('supportsStatistics', False) and
                    adv_query.get('supportsOrderBy', False) and
                    adv_query.get('supportsPagination', False)
                )
                
                if not has_optimization:
                    self.analysis_results["performance_checks"]["drawing_optimization"].append({
                        "layer": layer_info["title"],
                        "optimized": False,
                        "recommendation": "Consider enabling drawing optimization for improved performance",
                        "severity": "warning"
                    })
            
            # Check for tile caching
            if hasattr(feature_layer.properties, 'tileMaxRecordCount'):
                if feature_layer.properties.tileMaxRecordCount == 0:
                    self.analysis_results["performance_checks"]["drawing_optimization"].append({
                        "layer": layer_info["title"],
                        "issue": "Tile caching disabled",
                        "recommendation": "Enable tile caching for better performance at multiple scales",
                        "severity": "info"
                    })
                    
        except Exception as e:
            logger.debug(f"Could not check drawing optimization for {layer_info['title']}: {str(e)}")
    
    def _check_query_capabilities(self, feature_layer: FeatureLayer, layer_info: Dict):
        """Check if query capabilities are enabled for field apps."""
        try:
            capabilities = feature_layer.properties.capabilities if hasattr(feature_layer.properties, 'capabilities') else ""
            
            if not capabilities or 'Query' not in capabilities:
                self.analysis_results["performance_checks"]["query_capabilities"].append({
                    "layer": layer_info["title"],
                    "queryable": False,
                    "recommendation": "Enable query capabilities for field app compatibility",
                    "severity": "critical"
                })
                
        except Exception as e:
            logger.debug(f"Could not check query capabilities for {layer_info['title']}: {str(e)}")
    
    def _check_editable_status(self, feature_layer: FeatureLayer, layer_info: Dict, layer: Any):
        """Check if layers intended for data collection are editable."""
        try:
            capabilities = feature_layer.properties.capabilities if hasattr(feature_layer.properties, 'capabilities') else ""
            is_editable = 'Editing' in capabilities or 'Create' in capabilities or 'Update' in capabilities
            
            # Check if layer name suggests it should be editable
            editable_keywords = ['collection', 'survey', 'inspection', 'edit', 'input', 'form', 'entry']
            layer_name_lower = layer_info["title"].lower()
            
            suggests_editable = any(keyword in layer_name_lower for keyword in editable_keywords)
            
            if suggests_editable and not is_editable:
                self.analysis_results["configuration_analysis"]["editable_layers"].append({
                    "layer": layer_info["title"],
                    "editable": False,
                    "recommendation": "Layer name suggests data collection but editing is disabled",
                    "severity": "warning"
                })
                
        except Exception as e:
            logger.debug(f"Could not check editable status for {layer_info['title']}: {str(e)}")
    
    def _check_visibility_ranges(self, layer: Any, layer_info: Dict):
        """Check if visibility ranges are set appropriately."""
        try:
            min_scale = getattr(layer, 'minScale', None) or 0
            max_scale = getattr(layer, 'maxScale', None) or 0
            
            # Check if no scale limits are set (both are 0)
            if min_scale == 0 and max_scale == 0:
                self.analysis_results["performance_checks"]["visibility_ranges"].append({
                    "layer": layer_info["title"],
                    "min_scale": "No limit",
                    "max_scale": "No limit",
                    "recommendation": "Consider setting scale limits to improve performance at different zoom levels",
                    "severity": "info"
                })
            
            # Check for overly broad ranges
            elif min_scale > 0 and max_scale > 0:
                scale_range = min_scale / max_scale if max_scale > 0 else 0
                if scale_range > 1000:  # Very broad range
                    self.analysis_results["performance_checks"]["visibility_ranges"].append({
                        "layer": layer_info["title"],
                        "min_scale": min_scale,
                        "max_scale": max_scale,
                        "range_ratio": scale_range,
                        "recommendation": "Very broad visibility range may impact performance",
                        "severity": "warning"
                    })
                    
        except Exception as e:
            logger.debug(f"Could not check visibility ranges for {layer_info['title']}: {str(e)}")
    
    def _check_popup_configuration(self, layer: Any, layer_info: Dict):
        """Check if popups are properly configured."""
        try:
            # Check for popup info
            popup_info = getattr(layer, 'popupInfo', None)
            
            if not popup_info:
                self.analysis_results["configuration_analysis"]["popup_config"].append({
                    "layer": layer_info["title"],
                    "configured": False,
                    "recommendation": "No popup configured - users won't see attribute information",
                    "severity": "warning"
                })
            else:
                # Check popup configuration quality
                issues = []
                
                # Check if title is configured
                if not popup_info.get('title'):
                    issues.append("No popup title configured")
                
                # Check if fields are configured
                field_infos = popup_info.get('fieldInfos', [])
                if not field_infos:
                    issues.append("No fields configured in popup")
                else:
                    # Check for too many fields
                    visible_fields = [f for f in field_infos if f.get('visible', True)]
                    if len(visible_fields) > 15:
                        issues.append(f"Too many fields ({len(visible_fields)}) in popup may overwhelm users")
                
                if issues:
                    self.analysis_results["configuration_analysis"]["popup_config"].append({
                        "layer": layer_info["title"],
                        "configured": True,
                        "issues": issues,
                        "recommendation": "Optimize popup configuration for better user experience",
                        "severity": "info"
                    })
                    
        except Exception as e:
            logger.debug(f"Could not check popup configuration for {layer_info['title']}: {str(e)}")
    
    def _generate_recommendations(self):
        """Generate overall recommendations based on analysis."""
        results = self.analysis_results
        
        # Layer count recommendation
        layer_count = results["summary"]["total_layers"] + results["summary"]["total_tables"]
        if layer_count > 15:
            severity = "critical" if layer_count > 30 else "warning"
            results["recommendations"].append({
                "category": "Overall",
                "issue": f"High number of layers/tables ({layer_count})",
                "recommendation": "Consider creating multiple focused web maps instead of one complex map",
                "severity": severity
            })
        
        # Old layers recommendation
        if len(results["layer_optimization"]["old_layers"]) > 5:
            results["recommendations"].append({
                "category": "Maintenance",
                "issue": f"{len(results['layer_optimization']['old_layers'])} layers are over 2 years old",
                "recommendation": "Schedule a review of older layers to ensure they're still relevant and up-to-date",
                "severity": "info"
            })
        
        # Field naming recommendation
        if len(results["layer_optimization"]["reserved_keywords"]) > 0:
            total_fields = sum(len(item["fields"]) for item in results["layer_optimization"]["reserved_keywords"])
            results["recommendations"].append({
                "category": "Data Design",
                "issue": f"{total_fields} fields use reserved keywords",
                "recommendation": "Plan to rename fields during next data update to avoid conflicts",
                "severity": "warning"
            })
    
    def _calculate_summary(self):
        """Calculate summary statistics."""
        summary = self.analysis_results["summary"]
        
        # Count total issues
        total_issues = 0
        critical_issues = 0
        
        # Check all result categories
        for category in ["layer_optimization", "performance_checks", "configuration_analysis", "field_analysis"]:
            if category in self.analysis_results:
                for subcategory in self.analysis_results[category].values():
                    if isinstance(subcategory, list):
                        total_issues += len(subcategory)
                        # Count critical issues
                        for item in subcategory:
                            if isinstance(item, dict) and item.get("severity") == "critical":
                                critical_issues += 1
        
        summary["total_issues"] = total_issues
        summary["critical_issues"] = critical_issues
        
        # Add performance score (0-100)
        if summary["total_layers"] + summary["total_tables"] > 0:
            # Base score
            score = 100
            
            # Deduct for issues
            score -= critical_issues * 10
            score -= (total_issues - critical_issues) * 2
            
            # Deduct for too many layers
            if summary["total_layers"] + summary["total_tables"] > 15:
                score -= 10
            
            summary["performance_score"] = max(0, score)
        else:
            summary["performance_score"] = 0


def analyze_webmap(gis: GIS, webmap_item_id: str, debug_mode: bool = True) -> Dict[str, Any]:
    """
    Convenience function to analyze a web map.
    
    Args:
        gis: Authenticated GIS object
        webmap_item_id: The item ID of the web map to analyze
        debug_mode: If True, doesn't make actual changes
        
    Returns:
        Dictionary containing analysis results
    """
    analyzer = WebMapAnalyzer(gis, debug_mode)
    return analyzer.analyze_webmap(webmap_item_id)


if __name__ == "__main__":
    # Example usage
    import os
    
    # Get credentials from environment
    username = os.environ.get("ARCGIS_USERNAME", "")
    password = os.environ.get("ARCGIS_PASSWORD", "")
    
    if username and password:
        # Create GIS connection
        gis = GIS(username=username, password=password)
        
        # Example web map ID
        webmap_id = "YOUR_WEBMAP_ID_HERE"
        
        # Analyze the web map
        results = analyze_webmap(gis, webmap_id)
        
        # Print summary
        print(f"\nWeb Map Analysis Summary")
        print(f"========================")
        print(f"Title: {results['webmap_info'].get('title', 'Unknown')}")
        print(f"Total Layers: {results['summary']['total_layers']}")
        print(f"Total Tables: {results['summary']['total_tables']}")
        print(f"Total Issues: {results['summary']['total_issues']}")
        print(f"Critical Issues: {results['summary']['critical_issues']}")
        print(f"Performance Score: {results['summary']['performance_score']}/100")
    else:
        print("Please set ARCGIS_USERNAME and ARCGIS_PASSWORD environment variables")
