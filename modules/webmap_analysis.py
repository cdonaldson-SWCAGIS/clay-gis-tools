"""
Web Map Analysis Module for Streamlit
Provides UI for analyzing ArcGIS Online web maps for optimization opportunities.
"""

import streamlit as st
import logging
import json
import base64
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from src.analyze_webmap import WebMapAnalyzer, analyze_webmap
from src.analysis_reports import create_report

from modules.logging_config import get_logger

# Configure logging
logger = get_logger("webmap_analysis")

def show():
    """Display the Web Map Analysis interface."""
    st.title("Web Map Analysis")
    
    # Check authentication
    if not st.session_state.get("authenticated", False):
        st.warning("Please authenticate first to use this tool.")
        return
    
    gis = st.session_state.get("gis")
    if not gis:
        st.error("No GIS connection found. Please authenticate.")
        return
    
    st.markdown("""
    ## Analyze Web Maps for Optimization
    
    This tool analyzes your web maps to identify optimization opportunities and best practices.
    It checks for performance issues, configuration problems, and provides recommendations.
    """)
    
    # Session state cleanup
    if st.sidebar.button("🗑️ Clear Analysis Results"):
        if "analysis_results" in st.session_state:
            del st.session_state["analysis_results"]
        if "analysis_timestamp" in st.session_state:
            del st.session_state["analysis_timestamp"]
        st.sidebar.success("Results cleared!")
        st.rerun()
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["Analyze", "Results", "Help"])
    
    with tab1:
        show_analysis_tab(gis)
    
    with tab2:
        show_results_tab()
    
    with tab3:
        show_help_tab()

def show_analysis_tab(gis):
    """Show the analysis input tab."""
    st.header("Select Web Map to Analyze")
    
    # Web map selection method
    selection_method = st.radio(
        "How would you like to select a web map?",
        ["Enter Web Map ID", "Search for Web Map"],
        horizontal=True
    )
    
    webmap_item = None
    
    if selection_method == "Enter Web Map ID":
        webmap_id = st.text_input(
            "Web Map Item ID",
            placeholder="Enter the ArcGIS Online item ID",
            help="The 32-character alphanumeric ID of the web map"
        )
        
        if webmap_id:
            try:
                webmap_item = gis.content.get(webmap_id)
                if webmap_item:
                    if webmap_item.type != "Web Map":
                        st.error(f"Item is a {webmap_item.type}, not a Web Map")
                        webmap_item = None
                else:
                    st.error("Web map not found. Please check the ID.")
            except Exception as e:
                st.error(f"Error retrieving web map: {str(e)}")
    
    else:  # Search for Web Map
        search_query = st.text_input(
            "Search Query",
            placeholder="Enter search terms",
            help="Search for web maps by title, tags, or description"
        )
        
        if search_query:
            with st.spinner("Searching..."):
                try:
                    max_items = st.session_state.get("max_items", 25)
                    search_results = gis.content.search(
                        query=f"{search_query} type:'Web Map'",
                        max_items=max_items
                    )
                    
                    if search_results:
                        # Create a selection list
                        options = []
                        for item in search_results:
                            option = f"{item.title} (by {item.owner}, modified {datetime.fromtimestamp(item.modified/1000).strftime('%Y-%m-%d')})"
                            options.append((option, item))
                        
                        selected_option = st.selectbox(
                            "Select a web map",
                            options=[opt[0] for opt in options]
                        )
                        
                        # Find the selected item
                        for opt_text, item in options:
                            if opt_text == selected_option:
                                webmap_item = item
                                break
                    else:
                        st.info("No web maps found matching your search.")
                        
                except Exception as e:
                    st.error(f"Error searching: {str(e)}")
    
    # Display selected web map info
    if webmap_item:
        st.success(f"Selected: {webmap_item.title}")
        
        # Show web map details
        with st.expander("Web Map Details", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Title:** {webmap_item.title}")
                st.write(f"**Owner:** {webmap_item.owner}")
                st.write(f"**Item ID:** {webmap_item.id}")
                
            with col2:
                st.write(f"**Created:** {datetime.fromtimestamp(webmap_item.created/1000).strftime('%Y-%m-%d %H:%M')}")
                st.write(f"**Modified:** {datetime.fromtimestamp(webmap_item.modified/1000).strftime('%Y-%m-%d %H:%M')}")
                st.write(f"**Tags:** {', '.join(webmap_item.tags) if webmap_item.tags else 'None'}")
            
            if webmap_item.description:
                st.write(f"**Description:** {webmap_item.description}")
        
        # Analysis options
        st.subheader("Analysis Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Check categories
            st.write("**Select Analysis Categories:**")
            analyze_all = st.checkbox("Analyze All Categories", value=True)
            
            if not analyze_all:
                analyze_layers = st.checkbox("Layer Optimization", value=True)
                analyze_performance = st.checkbox("Performance Checks", value=True)
                analyze_config = st.checkbox("Configuration Analysis", value=True)
                analyze_fields = st.checkbox("Field Analysis", value=True)
            else:
                analyze_layers = True
                analyze_performance = True
                analyze_config = True
                analyze_fields = True
        
        with col2:
            # Thresholds
            st.write("**Analysis Thresholds:**")
            layer_threshold = st.number_input(
                "Layer Count Warning Threshold",
                min_value=5,
                max_value=50,
                value=15,
                help="Warn when web map has more than this many layers"
            )
            
            record_threshold = st.number_input(
                "Record Count Warning Threshold",
                min_value=1000,
                max_value=100000,
                value=10000,
                step=1000,
                help="Warn when a layer has more than this many records"
            )
        
        # Analyze button
        if st.button("Analyze Web Map", type="primary", use_container_width=True):
            analyze_webmap_with_progress(gis, webmap_item.id, {
                "analyze_layers": analyze_layers,
                "analyze_performance": analyze_performance,
                "analyze_config": analyze_config,
                "analyze_fields": analyze_fields,
                "layer_threshold": layer_threshold,
                "record_threshold": record_threshold
            })

def analyze_webmap_with_progress(gis, webmap_id: str, options: Dict[str, Any]):
    """Analyze a web map with progress indication."""
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        # Update progress
        progress_bar.progress(10)
        status_text.text("Initializing analysis...")
        
        # Get debug mode from session state
        debug_mode = st.session_state.get("debug_mode", True)
        
        # Create analyzer
        analyzer = WebMapAnalyzer(gis, debug_mode)
        
        # Update progress
        progress_bar.progress(20)
        status_text.text("Loading web map...")
        
        # Perform analysis
        results = analyzer.analyze_webmap(webmap_id)
        
        # Update progress
        progress_bar.progress(80)
        status_text.text("Generating report...")
        
        # Store results in session state
        st.session_state.analysis_results = results
        st.session_state.analysis_timestamp = datetime.now()
        
        # Complete
        progress_bar.progress(100)
        status_text.text("Analysis complete!")
        
        # Show summary
        show_analysis_summary(results)
        
    except Exception as e:
        st.error(f"Error during analysis: {str(e)}")
        logger.error(f"Analysis error: {str(e)}")
    finally:
        # Clear progress indicators
        progress_bar.empty()
        status_text.empty()

def show_analysis_summary(results: Dict[str, Any]):
    """Show a summary of the analysis results."""
    st.success("Analysis completed successfully!")
    
    # Performance score
    report_gen = create_report(results)
    score_info = report_gen.format_performance_score()
    
    # Display performance score with custom styling
    score_html = f"""
    <div style="text-align: center; padding: 20px; background-color: {score_info['color']}20; border-radius: 10px; margin: 20px 0;">
        <h1 style="margin: 0; color: {score_info['color']};">Performance Score: {score_info['score']}/100</h1>
        <h2 style="margin: 10px 0; color: {score_info['color']};">Grade: {score_info['grade']} - {score_info['status']}</h2>
    </div>
    """
    st.markdown(score_html, unsafe_allow_html=True)
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    summary = results.get("summary", {})
    
    with col1:
        st.metric("Total Layers", summary.get("total_layers", 0))
    
    with col2:
        st.metric("Total Tables", summary.get("total_tables", 0))
    
    with col3:
        st.metric("Total Issues", summary.get("total_issues", 0))
    
    with col4:
        st.metric("Critical Issues", summary.get("critical_issues", 0))
    
    # Navigate to results
    st.info("Navigate to the **Results** tab to view detailed findings and download reports.")

def show_results_tab():
    """Show the results tab."""
    if "analysis_results" not in st.session_state:
        st.info("No analysis results available. Please analyze a web map first.")
        return
    
    results = st.session_state.analysis_results
    timestamp = st.session_state.get("analysis_timestamp", datetime.now())
    
    st.header("Analysis Results")
    st.caption(f"Analysis performed: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create report generator
    report_gen = create_report(results)
    
    # Results navigation
    results_view = st.radio(
        "View",
        ["Summary", "Layer Details", "Issues by Category", "Visualizations", "Export"],
        horizontal=True
    )
    
    if results_view == "Summary":
        show_summary_view(report_gen)
    
    elif results_view == "Layer Details":
        show_layer_details_view(report_gen)
    
    elif results_view == "Issues by Category":
        show_category_view(results)
    
    elif results_view == "Visualizations":
        show_visualizations_view(report_gen)
    
    elif results_view == "Export":
        show_export_view(report_gen)

def show_summary_view(report_gen):
    """Show summary view of results."""
    # Display formatted summary report
    summary_report = report_gen.generate_summary_report()
    st.text(summary_report)

def show_layer_details_view(report_gen):
    """Show detailed layer analysis."""
    st.subheader("Layer Analysis Details")
    
    # Get layer summary table
    layer_df = report_gen.generate_layer_summary_table()
    
    if not layer_df.empty:
        # Style the dataframe
        def style_severity(val):
            if val > 0:
                if "Critical" in val.name:
                    return "background-color: #ffcccc"
                elif "Warnings" in val.name:
                    return "background-color: #ffffcc"
                elif "Info" in val.name:
                    return "background-color: #ccffcc"
            return ""
        
        styled_df = layer_df.style.applymap(
            style_severity,
            subset=["Critical", "Warnings", "Info"]
        )
        
        st.dataframe(styled_df, use_container_width=True)
        
        # Layer selection for detailed view
        if len(layer_df) > 0:
            selected_layer = st.selectbox(
                "Select a layer for detailed issues",
                layer_df["Layer"].tolist()
            )
            
            if selected_layer:
                show_layer_issues(selected_layer, report_gen.results)
    else:
        st.info("No layers found in the analysis.")

def show_layer_issues(layer_name: str, results: Dict[str, Any]):
    """Show all issues for a specific layer."""
    st.write(f"**Issues for: {layer_name}**")
    
    issues_found = False
    
    # Check all categories for this layer
    all_categories = ["layer_optimization", "performance_checks", "configuration_analysis", "field_analysis"]
    
    for category in all_categories:
        if category in results:
            for subcategory_name, subcategory_data in results[category].items():
                if isinstance(subcategory_data, list):
                    for item in subcategory_data:
                        if isinstance(item, dict) and item.get("layer") == layer_name:
                            issues_found = True
                            severity = item.get("severity", "info")
                            severity_icon = {
                                "critical": "🔴",
                                "warning": "🟡",
                                "info": "ℹ️"
                            }.get(severity, "ℹ️")
                            
                            with st.expander(f"{severity_icon} {subcategory_name.replace('_', ' ').title()}", expanded=True):
                                # Display issue details
                                for key, value in item.items():
                                    if key not in ["layer", "severity"]:
                                        if isinstance(value, list):
                                            st.write(f"**{key.replace('_', ' ').title()}:**")
                                            for v in value:
                                                st.write(f"  • {v}")
                                        else:
                                            st.write(f"**{key.replace('_', ' ').title()}:** {value}")
    
    if not issues_found:
        st.success("No issues found for this layer.")

def show_category_view(results: Dict[str, Any]):
    """Show issues organized by category."""
    st.subheader("Issues by Category")
    
    # Layer Optimization
    if "layer_optimization" in results:
        with st.expander("Layer Optimization", expanded=True):
            opt = results["layer_optimization"]
            
            # Record counts
            if opt.get("record_counts"):
                st.write("**Record Counts:**")
                for record in opt["record_counts"]:
                    if record.get("performance_impact") in ["medium", "high"]:
                        st.warning(f"• {record['layer']}: {record['count']:,} records ({record['performance_impact']} impact)")
            
            # Old layers
            if opt.get("old_layers"):
                st.write("**Layers Over 2 Years Old:**")
                for layer in opt["old_layers"]:
                    st.info(f"• {layer['layer']}: {layer['age_years']} years old")
            
            # Reserved keywords
            if opt.get("reserved_keywords"):
                st.write("**Reserved Keywords in Field Names:**")
                for item in opt["reserved_keywords"]:
                    fields = [f['field'] for f in item['fields']]
                    st.warning(f"• {item['layer']}: {', '.join(fields)}")
    
    # Performance Checks
    if "performance_checks" in results:
        with st.expander("Performance Checks", expanded=True):
            perf = results["performance_checks"]
            
            # Drawing optimization
            if perf.get("drawing_optimization"):
                st.write("**Drawing Optimization Issues:**")
                for item in perf["drawing_optimization"]:
                    st.warning(f"• {item['layer']}: {item.get('issue', 'Not optimized')}")
            
            # Query capabilities
            if perf.get("query_capabilities"):
                st.write("**Query Capability Issues:**")
                for item in perf["query_capabilities"]:
                    if not item.get("queryable", True):
                        st.error(f"• {item['layer']}: Query not enabled (critical for field apps)")
            
            # Visibility ranges
            if perf.get("visibility_ranges"):
                st.write("**Visibility Range Issues:**")
                for item in perf["visibility_ranges"]:
                    st.info(f"• {item['layer']}: {item.get('recommendation', 'Check visibility ranges')}")
    
    # Configuration Analysis
    if "configuration_analysis" in results:
        with st.expander("Configuration Analysis", expanded=True):
            config = results["configuration_analysis"]
            
            # Popup configuration
            if config.get("popup_config"):
                st.write("**Popup Configuration Issues:**")
                for item in config["popup_config"]:
                    issues = item.get("issues", ["No popup configured"])
                    st.warning(f"• {item['layer']}: {'; '.join(issues)}")
            
            # Editable layers
            if config.get("editable_layers"):
                st.write("**Editable Layer Issues:**")
                for item in config["editable_layers"]:
                    st.warning(f"• {item['layer']}: {item.get('recommendation', 'Check edit capabilities')}")
    
    # Field Analysis
    if "field_analysis" in results:
        with st.expander("Field Analysis", expanded=True):
            field = results["field_analysis"]
            
            # Alias issues
            if field.get("alias_issues"):
                st.write("**Field Alias Issues:**")
                for item in field["alias_issues"]:
                    st.info(f"• {item['layer']}: {len(item.get('fields', []))} fields need aliases")

def show_visualizations_view(report_gen):
    """Show data visualizations."""
    st.subheader("Analysis Visualizations")
    
    # Issue breakdown pie chart
    col1, col2 = st.columns(2)
    
    with col1:
        # Severity breakdown
        severity_data = report_gen.generate_severity_summary()
        if any(severity_data.values()):
            fig_severity = go.Figure(data=[go.Pie(
                labels=["Critical", "Warning", "Info"],
                values=[severity_data["critical"], severity_data["warning"], severity_data["info"]],
                marker_colors=["#ff4444", "#ffaa44", "#4444ff"]
            )])
            fig_severity.update_layout(title="Issues by Severity")
            st.plotly_chart(fig_severity, use_container_width=True)
    
    with col2:
        # Category breakdown
        category_data = report_gen.generate_issue_breakdown()
        categories = [k for k, v in category_data.items() if v > 0]
        values = [v for v in category_data.values() if v > 0]
        
        if categories:
            fig_category = go.Figure(data=[go.Bar(
                x=values,
                y=categories,
                orientation='h',
                marker_color='lightblue'
            )])
            fig_category.update_layout(
                title="Issues by Category",
                xaxis_title="Number of Issues",
                yaxis_title="Category"
            )
            st.plotly_chart(fig_category, use_container_width=True)
    
    # Layer performance scatter plot
    layer_df = report_gen.generate_layer_summary_table()
    if not layer_df.empty and len(layer_df) > 0:
        fig_scatter = px.scatter(
            layer_df,
            x="Records",
            y="Issues",
            size="Issues",
            color="Critical",
            hover_data=["Layer", "Warnings", "Info"],
            title="Layer Performance Overview",
            labels={
                "Records": "Number of Records",
                "Issues": "Total Issues",
                "Critical": "Critical Issues"
            }
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

def show_export_view(report_gen):
    """Show export options."""
    st.subheader("Export Analysis Results")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Text report
        st.write("**Summary Report (Text)**")
        text_report = report_gen.generate_summary_report()
        st.download_button(
            label="Download Text Report",
            data=text_report,
            file_name=f"webmap_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            mime="text/plain"
        )
    
    with col2:
        # CSV report
        st.write("**Detailed Report (CSV)**")
        csv_report = report_gen.generate_detailed_csv()
        st.download_button(
            label="Download CSV Report",
            data=csv_report,
            file_name=f"webmap_analysis_details_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col3:
        # JSON export
        st.write("**Full Results (JSON)**")
        json_export = report_gen.generate_json_export()
        st.download_button(
            label="Download JSON Export",
            data=json_export,
            file_name=f"webmap_analysis_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    # Display JSON preview
    with st.expander("Preview JSON Export"):
        st.json(report_gen.results)

def show_help_tab():
    """Show help information."""
    st.header("Web Map Analysis Help")
    
    st.markdown("""
    ### Overview
    
    The Web Map Analysis tool examines your ArcGIS Online web maps to identify optimization 
    opportunities and ensure best practices are followed. It provides actionable recommendations 
    to improve performance and user experience.
    
    ### Analysis Categories
    
    #### 1. Layer Optimization
    - **Record Counts**: Reports the number of records in each queryable layer
    - **Layer Age**: Identifies layers created more than 2 years ago
    - **Reserved Keywords**: Checks for field names that use SQL or ArcGIS reserved words
    - **Layer Count**: Warns when web maps have too many layers (default threshold: 15)
    
    #### 2. Performance Checks
    - **Drawing Optimization**: Verifies if optimized layer drawing is enabled
    - **Query Capabilities**: Ensures layers support queries for field app compatibility
    - **Visibility Ranges**: Checks if appropriate scale dependencies are set
    
    #### 3. Configuration Analysis
    - **Popup Configuration**: Evaluates popup settings and field visibility
    - **Editable Layers**: Identifies layers that may need edit capabilities
    
    #### 4. Field Analysis
    - **Meaningful Aliases**: Checks if fields have user-friendly aliases
    - **Field Structure**: Analyzes field naming conventions
    
    ### Performance Score
    
    The tool calculates a performance score (0-100) based on:
    - Number and severity of issues found
    - Total layer/table count
    - Critical issues have the highest impact
    
    **Score Grades:**
    - A (90-100): Excellent - Web map is well-optimized
    - B (80-89): Good - Minor improvements recommended
    - C (70-79): Fair - Several optimizations needed
    - D (60-69): Poor - Significant issues to address
    - F (0-59): Critical - Major optimization required
    
    ### Best Practices
    
    1. **Keep layer counts reasonable** - Aim for 15 or fewer layers per web map
    2. **Use meaningful field aliases** - Help users understand data
    3. **Enable query capabilities** - Required for Field Maps and other apps
    4. **Set visibility ranges** - Improve performance at different scales
    5. **Configure popups** - Enhance user experience with relevant information
    6. **Review old layers** - Keep content current and relevant
    7. **Avoid reserved keywords** - Prevent potential conflicts
    
    ### Troubleshooting
    
    - **Analysis fails**: Check that you have access to the web map and all its layers
    - **No results**: Ensure the web map contains operational layers
    - **Performance issues**: Large web maps may take longer to analyze
    """)
