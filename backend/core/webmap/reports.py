"""
Web Map Analysis Report Generation
Formats analysis results for display and export.
"""

import json
import csv
import io
from datetime import datetime
from typing import Dict, Any, List, Optional
import pandas as pd


class AnalysisReportGenerator:
    """Generates formatted reports from web map analysis results."""
    
    def __init__(self, analysis_results: Dict[str, Any]):
        """
        Initialize the report generator.
        
        Args:
            analysis_results: Dictionary containing analysis results
        """
        self.results = analysis_results
        
    def generate_summary_report(self) -> str:
        """Generate a text summary report."""
        report = []
        
        # Header
        report.append("=" * 80)
        report.append("WEB MAP ANALYSIS REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        # Web Map Information
        info = self.results.get("webmap_info", {})
        report.append("WEB MAP INFORMATION")
        report.append("-" * 40)
        report.append(f"Title: {info.get('title', 'Unknown')}")
        report.append(f"ID: {info.get('id', 'Unknown')}")
        report.append(f"Owner: {info.get('owner', 'Unknown')}")
        report.append(f"Created: {info.get('created', 'Unknown')}")
        report.append(f"Modified: {info.get('modified', 'Unknown')}")
        report.append(f"Tags: {', '.join(info.get('tags', []))}")
        report.append("")
        
        # Summary Statistics
        summary = self.results.get("summary", {})
        report.append("SUMMARY STATISTICS")
        report.append("-" * 40)
        report.append(f"Total Layers: {summary.get('total_layers', 0)}")
        report.append(f"Total Tables: {summary.get('total_tables', 0)}")
        report.append(f"Total Issues: {summary.get('total_issues', 0)}")
        report.append(f"Critical Issues: {summary.get('critical_issues', 0)}")
        report.append(f"Performance Score: {summary.get('performance_score', 0)}/100")
        report.append("")
        
        # Critical Issues
        critical_issues = self._get_issues_by_severity("critical")
        if critical_issues:
            report.append("CRITICAL ISSUES")
            report.append("-" * 40)
            for issue in critical_issues:
                report.append(f"• {issue}")
            report.append("")
        
        # Recommendations
        recommendations = self.results.get("recommendations", [])
        if recommendations:
            report.append("RECOMMENDATIONS")
            report.append("-" * 40)
            for rec in recommendations:
                report.append(f"[{rec.get('severity', 'info').upper()}] {rec.get('category', 'General')}")
                report.append(f"  Issue: {rec.get('issue', '')}")
                report.append(f"  Recommendation: {rec.get('recommendation', '')}")
                report.append("")
        
        return "\n".join(report)
    
    def generate_detailed_csv(self) -> str:
        """Generate a detailed CSV report."""
        rows = []
        
        # Layer optimization issues
        for record in self.results.get("layer_optimization", {}).get("record_counts", []):
            rows.append({
                "Category": "Record Count",
                "Layer/Table": record.get("layer"),
                "Type": record.get("type"),
                "Issue": f"{record.get('count', 0):,} records",
                "Severity": record.get("performance_impact", "low"),
                "Recommendation": "Consider optimization" if record.get("count", 0) > 10000 else "OK"
            })
        
        for record in self.results.get("layer_optimization", {}).get("old_layers", []):
            rows.append({
                "Category": "Layer Age",
                "Layer/Table": record.get("layer"),
                "Type": "layer",
                "Issue": f"{record.get('age_years', 0)} years old",
                "Severity": "info",
                "Recommendation": record.get("recommendation", "")
            })
        
        for record in self.results.get("layer_optimization", {}).get("reserved_keywords", []):
            for field in record.get("fields", []):
                rows.append({
                    "Category": "Reserved Keyword",
                    "Layer/Table": record.get("layer"),
                    "Type": "field",
                    "Issue": f"Field '{field.get('field')}' uses reserved keyword",
                    "Severity": record.get("severity", "warning"),
                    "Recommendation": record.get("recommendation", "")
                })
        
        # Performance checks
        for record in self.results.get("performance_checks", {}).get("drawing_optimization", []):
            rows.append({
                "Category": "Drawing Optimization",
                "Layer/Table": record.get("layer"),
                "Type": "layer",
                "Issue": record.get("issue", "Not optimized"),
                "Severity": record.get("severity", "warning"),
                "Recommendation": record.get("recommendation", "")
            })
        
        for record in self.results.get("performance_checks", {}).get("query_capabilities", []):
            rows.append({
                "Category": "Query Capabilities",
                "Layer/Table": record.get("layer"),
                "Type": "layer",
                "Issue": "Query not enabled" if not record.get("queryable") else "OK",
                "Severity": record.get("severity", "critical"),
                "Recommendation": record.get("recommendation", "")
            })
        
        # Configuration issues
        for record in self.results.get("configuration_analysis", {}).get("popup_config", []):
            issues = record.get("issues", [])
            issue_text = "; ".join(issues) if issues else "No popup configured"
            rows.append({
                "Category": "Popup Configuration",
                "Layer/Table": record.get("layer"),
                "Type": "layer",
                "Issue": issue_text,
                "Severity": record.get("severity", "warning"),
                "Recommendation": record.get("recommendation", "")
            })
        
        # Field analysis
        for record in self.results.get("field_analysis", {}).get("alias_issues", []):
            for field in record.get("fields", []):
                rows.append({
                    "Category": "Field Alias",
                    "Layer/Table": record.get("layer"),
                    "Type": "field",
                    "Issue": f"Field '{field.get('field')}' needs alias",
                    "Severity": record.get("severity", "info"),
                    "Recommendation": f"Suggested: {field.get('suggested', '')}"
                })
        
        # Convert to CSV
        if rows:
            df = pd.DataFrame(rows)
            return df.to_csv(index=False)
        else:
            return "Category,Layer/Table,Type,Issue,Severity,Recommendation\nNo issues found,,,,,"
    
    def generate_json_export(self) -> str:
        """Generate a JSON export of the full analysis results."""
        return json.dumps(self.results, indent=2)
    
    def generate_layer_summary_table(self) -> pd.DataFrame:
        """Generate a summary table of all layers and their issues."""
        layer_data = {}
        
        # Collect all layers
        for record in self.results.get("layer_optimization", {}).get("record_counts", []):
            layer_name = record.get("layer")
            if layer_name not in layer_data:
                layer_data[layer_name] = {
                    "Layer": layer_name,
                    "Type": record.get("type", "layer"),
                    "Records": record.get("count", 0),
                    "Issues": 0,
                    "Critical": 0,
                    "Warnings": 0,
                    "Info": 0
                }
        
        # Count issues by layer
        all_categories = ["layer_optimization", "performance_checks", "configuration_analysis", "field_analysis"]
        
        for category in all_categories:
            if category in self.results:
                for subcategory in self.results[category].values():
                    if isinstance(subcategory, list):
                        for item in subcategory:
                            if isinstance(item, dict):
                                layer_name = item.get("layer")
                                severity = item.get("severity", "info")
                                
                                if layer_name:
                                    if layer_name not in layer_data:
                                        layer_data[layer_name] = {
                                            "Layer": layer_name,
                                            "Type": "layer",
                                            "Records": 0,
                                            "Issues": 0,
                                            "Critical": 0,
                                            "Warnings": 0,
                                            "Info": 0
                                        }
                                    
                                    layer_data[layer_name]["Issues"] += 1
                                    
                                    if severity == "critical":
                                        layer_data[layer_name]["Critical"] += 1
                                    elif severity == "warning":
                                        layer_data[layer_name]["Warnings"] += 1
                                    else:
                                        layer_data[layer_name]["Info"] += 1
        
        # Convert to DataFrame
        if layer_data:
            df = pd.DataFrame(list(layer_data.values()))
            # Sort by number of critical issues, then warnings, then total issues
            df = df.sort_values(by=["Critical", "Warnings", "Issues"], ascending=False)
            return df
        else:
            return pd.DataFrame(columns=["Layer", "Type", "Records", "Issues", "Critical", "Warnings", "Info"])
    
    def generate_issue_breakdown(self) -> Dict[str, int]:
        """Generate a breakdown of issues by category."""
        breakdown = {
            "Record Count": 0,
            "Layer Age": 0,
            "Reserved Keywords": 0,
            "Field Aliases": 0,
            "Drawing Optimization": 0,
            "Query Capabilities": 0,
            "Visibility Ranges": 0,
            "Popup Configuration": 0,
            "Editable Layers": 0
        }
        
        # Count issues in each category
        opt = self.results.get("layer_optimization", {})
        breakdown["Record Count"] = len([r for r in opt.get("record_counts", []) if r.get("count", 0) > 5000])
        breakdown["Layer Age"] = len(opt.get("old_layers", []))
        breakdown["Reserved Keywords"] = sum(len(r.get("fields", [])) for r in opt.get("reserved_keywords", []))
        
        perf = self.results.get("performance_checks", {})
        breakdown["Drawing Optimization"] = len(perf.get("drawing_optimization", []))
        breakdown["Query Capabilities"] = len([r for r in perf.get("query_capabilities", []) if not r.get("queryable", True)])
        breakdown["Visibility Ranges"] = len(perf.get("visibility_ranges", []))
        
        config = self.results.get("configuration_analysis", {})
        breakdown["Popup Configuration"] = len(config.get("popup_config", []))
        breakdown["Editable Layers"] = len(config.get("editable_layers", []))
        
        field = self.results.get("field_analysis", {})
        breakdown["Field Aliases"] = sum(len(r.get("fields", [])) for r in field.get("alias_issues", []))
        
        return breakdown
    
    def generate_severity_summary(self) -> Dict[str, int]:
        """Generate a summary of issues by severity."""
        severity_count = {
            "critical": 0,
            "warning": 0,
            "info": 0
        }
        
        # Count issues by severity
        all_categories = ["layer_optimization", "performance_checks", "configuration_analysis", "field_analysis"]
        
        for category in all_categories:
            if category in self.results:
                for subcategory in self.results[category].values():
                    if isinstance(subcategory, list):
                        for item in subcategory:
                            if isinstance(item, dict):
                                severity = item.get("severity", "info")
                                if severity in severity_count:
                                    severity_count[severity] += 1
        
        return severity_count
    
    def _get_issues_by_severity(self, severity: str) -> List[str]:
        """Get all issues of a specific severity level."""
        issues = []
        
        all_categories = ["layer_optimization", "performance_checks", "configuration_analysis", "field_analysis"]
        
        for category in all_categories:
            if category in self.results:
                for subcategory_name, subcategory_data in self.results[category].items():
                    if isinstance(subcategory_data, list):
                        for item in subcategory_data:
                            if isinstance(item, dict) and item.get("severity") == severity:
                                layer = item.get("layer", "Unknown")
                                
                                if subcategory_name == "reserved_keywords":
                                    fields = [f.get("field") for f in item.get("fields", [])]
                                    issues.append(f"{layer}: Reserved keywords in fields {', '.join(fields)}")
                                elif subcategory_name == "query_capabilities":
                                    issues.append(f"{layer}: Query capabilities not enabled")
                                elif subcategory_name == "drawing_optimization":
                                    issues.append(f"{layer}: Drawing optimization not enabled")
                                else:
                                    issues.append(f"{layer}: {item.get('issue', 'Issue detected')}")
        
        # Also check recommendations
        for rec in self.results.get("recommendations", []):
            if rec.get("severity") == severity:
                if "layer" in rec:
                    issues.append(f"{rec.get('layer')}: {rec.get('issue', '')}")
                else:
                    issues.append(rec.get("issue", ""))
        
        return issues
    
    def format_performance_score(self) -> Dict[str, Any]:
        """Format the performance score with color and grade."""
        score = self.results.get("summary", {}).get("performance_score", 0)
        
        if score >= 90:
            grade = "A"
            color = "green"
            status = "Excellent"
        elif score >= 80:
            grade = "B"
            color = "lightgreen"
            status = "Good"
        elif score >= 70:
            grade = "C"
            color = "yellow"
            status = "Fair"
        elif score >= 60:
            grade = "D"
            color = "orange"
            status = "Poor"
        else:
            grade = "F"
            color = "red"
            status = "Critical"
        
        return {
            "score": score,
            "grade": grade,
            "color": color,
            "status": status
        }


def create_report(analysis_results: Dict[str, Any]) -> AnalysisReportGenerator:
    """
    Create a report generator instance.
    
    Args:
        analysis_results: Dictionary containing analysis results
        
    Returns:
        AnalysisReportGenerator instance
    """
    return AnalysisReportGenerator(analysis_results)
