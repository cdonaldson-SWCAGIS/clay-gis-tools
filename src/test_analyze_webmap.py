"""
Test script for the Web Map Analysis tool
Demonstrates usage and functionality.
"""

import os
import json
from arcgis.gis import GIS
from analyze_webmap import WebMapAnalyzer, analyze_webmap
from analysis_reports import create_report

def test_webmap_analysis():
    """Test the web map analysis functionality."""
    
    # Get credentials from environment
    username = os.environ.get("ARCGIS_USERNAME", "fdc_admin_swca")
    password = os.environ.get("ARCGIS_PASSWORD", "EarthRouser24")
    
    print("Connecting to ArcGIS Online...")
    try:
        gis = GIS(username=username, password=password)
        print(f"Connected as: {gis.properties.user.username}")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return
    
    # Example web map ID - replace with an actual web map ID
    webmap_id = "YOUR_WEBMAP_ID_HERE"  # Replace this with a real web map ID
    
    # You can also search for web maps
    print("\nSearching for example web maps...")
    search_results = gis.content.search("title:* AND type:'Web Map'", max_items=5)
    
    if search_results:
        print(f"Found {len(search_results)} web maps:")
        for i, item in enumerate(search_results):
            print(f"  {i+1}. {item.title} (ID: {item.id})")
        
        # Use the first result for testing
        webmap_id = search_results[0].id
        print(f"\nUsing web map: {search_results[0].title}")
    else:
        print("No web maps found. Please provide a web map ID.")
        return
    
    # Run analysis
    print(f"\nAnalyzing web map ID: {webmap_id}")
    print("-" * 50)
    
    # Create analyzer (debug mode = True for safety)
    analyzer = WebMapAnalyzer(gis, debug_mode=True)
    
    # Perform analysis
    try:
        results = analyzer.analyze_webmap(webmap_id)
        
        # Display summary
        print("\nANALYSIS SUMMARY")
        print("=" * 50)
        
        info = results.get("webmap_info", {})
        print(f"Title: {info.get('title', 'Unknown')}")
        print(f"Owner: {info.get('owner', 'Unknown')}")
        print(f"Created: {info.get('created', 'Unknown')}")
        print(f"Modified: {info.get('modified', 'Unknown')}")
        
        summary = results.get("summary", {})
        print(f"\nStatistics:")
        print(f"  Total Layers: {summary.get('total_layers', 0)}")
        print(f"  Total Tables: {summary.get('total_tables', 0)}")
        print(f"  Total Issues: {summary.get('total_issues', 0)}")
        print(f"  Critical Issues: {summary.get('critical_issues', 0)}")
        print(f"  Performance Score: {summary.get('performance_score', 0)}/100")
        
        # Show record counts
        record_counts = results.get("layer_optimization", {}).get("record_counts", [])
        if record_counts:
            print("\nRECORD COUNTS:")
            for record in record_counts:
                print(f"  • {record['layer']}: {record['count']:,} records ({record['performance_impact']} impact)")
        
        # Show old layers
        old_layers = results.get("layer_optimization", {}).get("old_layers", [])
        if old_layers:
            print("\nLAYERS OVER 2 YEARS OLD:")
            for layer in old_layers:
                print(f"  • {layer['layer']}: {layer['age_years']} years old")
        
        # Show reserved keywords
        reserved_keywords = results.get("layer_optimization", {}).get("reserved_keywords", [])
        if reserved_keywords:
            print("\nRESERVED KEYWORDS FOUND:")
            for item in reserved_keywords:
                fields = [f['field'] for f in item['fields']]
                print(f"  • {item['layer']}: {', '.join(fields)}")
        
        # Show recommendations
        recommendations = results.get("recommendations", [])
        if recommendations:
            print("\nRECOMMENDATIONS:")
            for rec in recommendations:
                print(f"  [{rec['severity'].upper()}] {rec['category']}")
                print(f"    Issue: {rec['issue']}")
                print(f"    Action: {rec['recommendation']}")
        
        # Generate reports
        print("\nGENERATING REPORTS...")
        report_gen = create_report(results)
        
        # Save text report
        text_report = report_gen.generate_summary_report()
        with open("webmap_analysis_report.txt", "w") as f:
            f.write(text_report)
        print("  ✓ Saved text report to webmap_analysis_report.txt")
        
        # Save CSV report
        csv_report = report_gen.generate_detailed_csv()
        with open("webmap_analysis_details.csv", "w") as f:
            f.write(csv_report)
        print("  ✓ Saved CSV report to webmap_analysis_details.csv")
        
        # Save JSON export
        json_export = report_gen.generate_json_export()
        with open("webmap_analysis_full.json", "w") as f:
            f.write(json_export)
        print("  ✓ Saved JSON export to webmap_analysis_full.json")
        
        # Performance score interpretation
        score_info = report_gen.format_performance_score()
        print(f"\nPERFORMANCE GRADE: {score_info['grade']} - {score_info['status']}")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()


def demonstrate_analyzer_methods():
    """Demonstrate individual analyzer methods."""
    print("\nDEMONSTRATING ANALYZER METHODS")
    print("=" * 50)
    
    # This shows how individual checks work
    from analyze_webmap import RESERVED_KEYWORDS, CRYPTIC_FIELD_PATTERNS
    
    print("\nRESERVED KEYWORDS (sample):")
    keywords_sample = list(RESERVED_KEYWORDS)[:10]
    print(f"  {', '.join(keywords_sample)}...")
    print(f"  Total: {len(RESERVED_KEYWORDS)} keywords")
    
    print("\nCRYPTIC FIELD PATTERNS:")
    for pattern, replacement in list(CRYPTIC_FIELD_PATTERNS.items())[:5]:
        print(f"  '{pattern}' → '{replacement}'")
    
    # Show alias suggestions
    from analyze_webmap import WebMapAnalyzer
    analyzer = WebMapAnalyzer(None, debug_mode=True)  # No GIS needed for this demo
    
    print("\nFIELD ALIAS SUGGESTIONS:")
    test_fields = ["fld_name", "dt_created", "num_items", "addr_street", "project_desc"]
    for field in test_fields:
        suggested = analyzer._suggest_alias(field)
        print(f"  '{field}' → '{suggested}'")


if __name__ == "__main__":
    print("WEB MAP ANALYSIS TOOL - TEST SCRIPT")
    print("=" * 50)
    
    # Run the main test
    test_webmap_analysis()
    
    # Show additional demonstrations
    demonstrate_analyzer_methods()
    
    print("\nTest complete!")
