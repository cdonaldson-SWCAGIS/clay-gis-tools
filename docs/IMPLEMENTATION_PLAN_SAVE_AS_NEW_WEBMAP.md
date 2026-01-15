# Implementation Plan: Save as New Web Map Feature

## Executive Summary

**Feature**: Save as New Web Map  
**Purpose**: Allow users to duplicate existing web maps with a configurable title suffix  
**Primary Location**: Add new tab to `frontend/page_modules/webmap_forms.py`  
**Backend Function**: `backend/core/webmap/utils.py` - `copy_webmap_as_new()`  
**Key Technology**: ArcGIS Python API `Map.save()` method  
**Settings**: `MAP_SUFFIX` environment variable (default: "_Copy")  
**Estimated Complexity**: Medium (3-4 hours implementation)

## Overview
This document outlines the implementation plan for adding a "Save as New Web Map" feature that allows users to duplicate an existing web map with a configurable suffix appended to the title. The feature will use the ArcGIS Python API's `Map.save()` method to create a new web map item, and will provide a clickable link to the newly created map in the user's portal.

## Feature Requirements

1. **Save as New Web Map**: Create a copy of an existing web map with a new title
2. **MAP_SUFFIX Setting**: Configurable suffix via environment variable or settings
3. **Default Title Format**: `<Original Map Title>_<MAP_SUFFIX>`
4. **Portal Link**: Display a clickable link to the newly created web map using the authenticated user's portal URL

## Implementation Components

### 1. Backend: Web Map Copy Function
**Location**: `backend/core/webmap/utils.py` or new file `backend/core/webmap/copy.py`

**Function Signature**:
```python
def copy_webmap_as_new(
    source_webmap_id: str,
    gis: GIS,
    new_title: Optional[str] = None,
    map_suffix: Optional[str] = None,
    debug_mode: bool = False
) -> Dict[str, Any]:
    """
    Create a copy of a web map with a new title using the Map.save() method.
    
    Args:
        source_webmap_id: ID of the source web map to copy
        gis: Authenticated GIS object
        new_title: Custom title for the new web map (if None, uses <original>_<suffix>)
        map_suffix: Suffix to append to title (if None, uses MAP_SUFFIX env var)
        debug_mode: If True, simulate the operation without creating the map
        
    Returns:
        Dictionary containing:
        - success: bool
        - new_webmap_id: str (if successful)
        - new_webmap_title: str
        - portal_url: str (link to the new web map)
        - message: str
        - source_webmap_title: str (for reference)
    """
    
    # Implementation example:
    from arcgis.map import Map
    from frontend.components.common_operations import get_environment_setting
    
    # Get source web map
    source_item = get_webmap_item(source_webmap_id, gis)
    
    # Determine new title
    if not new_title:
        suffix = map_suffix or get_environment_setting("MAP_SUFFIX", "_Copy")
        new_title = f"{source_item.title}{suffix}"
    
    if debug_mode:
        return {
            "success": True,
            "new_webmap_id": None,
            "new_webmap_title": new_title,
            "portal_url": None,
            "message": f"DEBUG: Would create web map '{new_title}'",
            "source_webmap_title": source_item.title
        }
    
    # Create Map object and save as new
    map_obj = Map(source_item)
    item_props = {
        "title": new_title,
        "snippet": source_item.description or f"Copy of {source_item.title}",
        "tags": (source_item.tags or []) + ["copied", "save_as_new"]
    }
    new_item = map_obj.save(item_props)
    
    # Get portal URL and construct link
    portal_url = get_portal_url(gis)
    item_url = f"{portal_url}/home/item.html?id={new_item.id}"
    
    return {
        "success": True,
        "new_webmap_id": new_item.id,
        "new_webmap_title": new_item.title,
        "portal_url": item_url,
        "message": f"Successfully created web map '{new_title}'",
        "source_webmap_title": source_item.title
    }
```

**Implementation Steps**:
1. Retrieve source web map using `get_webmap_item()`
2. Determine new title:
   - If `new_title` provided, use it
   - Otherwise, use `<original_title>_<map_suffix>`
   - Get `map_suffix` from parameter or `MAP_SUFFIX` env var (default: "_Copy")
3. Create new web map item using `Map` class:
   - Import: `from arcgis.map import Map`
   - Create Map object from source: `map_obj = Map(source_webmap_item)`
   - Save as new item: `new_item = map_obj.save(item_properties)`
   - Item properties should include: title, snippet (description), tags
4. Get portal URL from `gis.properties.url` or `gis.url`
5. Construct full URL: `{portal_url}/home/item.html?id={new_webmap_id}`
6. Return result dictionary

**Note**: The `Map.save()` method automatically creates a new web map item with all layers and configurations from the source. This is the recommended approach per ArcGIS Python API documentation.

### 2. Settings Configuration
**Location**: `modules/settings.py` or `frontend/page_modules/settings.py`

**Add to Settings UI**:
- Add "MAP_SUFFIX" field in General or Advanced settings tab
- Store in environment variable or session state
- Default value: "_Copy" (configurable)
- Allow user to customize the suffix used for copied web maps

**Environment Variable**:
- Add `MAP_SUFFIX` to `.env.example` (if exists) or documentation
- Read via `get_environment_setting("MAP_SUFFIX", default_value="")`

### 3. Frontend: UI Component
**Location**: `frontend/page_modules/webmap_forms.py` or new dedicated page

**Option A: Add to Web Map Forms Page**
- Add new tab "Save as New" alongside existing tabs
- Reuse existing `ItemSelector` for web map selection
- Add text input for custom title (optional, with default preview)
- Show preview of new title: `<selected_map_title>_<MAP_SUFFIX>`
- Add "Save as New Web Map" button
- Display results with link to new web map

**Option B: Add to Web Map Analysis Page**
- Add section at bottom of analysis results
- "Actions" section with "Save as New" button

**Option C: Create New Page**
- New navigation item: "Web Map Tools" or "Web Map Utilities"
- Include "Save as New" as primary feature
- Can expand later with other utilities

**Recommended**: Option A (add to Web Map Forms) - most logical place since users are already working with web maps there.

### 4. UI Implementation Details

**Component Structure**:
```python
def show_save_as_new():
    """Display the Save as New Web Map interface"""
    # Get GIS object
    gis = get_gis_object()
    if not gis:
        return
    
    # Web map selection
    item_selector = ItemSelector(gis, "Web Map", "save_as_new")
    selected_webmap = item_selector.show(...)
    
    if not selected_webmap:
        return
    
    # Get MAP_SUFFIX from settings
    map_suffix = get_environment_setting("MAP_SUFFIX", "")
    
    # Title input with preview
    st.subheader("New Web Map Title")
    default_title = f"{selected_webmap.title}_{map_suffix}" if map_suffix else f"{selected_webmap.title}_Copy"
    custom_title = st.text_input(
        "Title (optional)",
        value=default_title,
        help="Leave blank to use default: <Original Title>_<Suffix>"
    )
    
    # Debug mode control
    debug_mode = show_debug_mode_control("save_as_new")
    
    # Execute button
    if st.button("Save as New Web Map", type="primary"):
        # Execute copy operation
        result = execute_save_as_new(
            selected_webmap.id,
            custom_title if custom_title else None,
            gis,
            debug_mode
        )
        
        # Display results with link
        if result and result.get("success"):
            st.success(f"Successfully created new web map: {result['new_webmap_title']}")
            st.markdown(f"[Open in Portal]({result['portal_url']})")
```

### 5. Portal URL Construction

**Get Portal URL**:
```python
def get_portal_url(gis: GIS) -> str:
    """Get the portal URL for the authenticated user"""
    # Try multiple methods to get portal URL
    if hasattr(gis, 'url'):
        portal_url = gis.url
    elif hasattr(gis, 'properties') and hasattr(gis.properties, 'url'):
        portal_url = gis.properties.url
    else:
        # Fallback: construct from username/org
        # This is less reliable but provides a fallback
        portal_url = "https://www.arcgis.com"  # Default to AGOL
    
    # Ensure URL doesn't end with slash
    return portal_url.rstrip('/')
```

**Note**: The portal URL format may vary:
- ArcGIS Online: `https://www.arcgis.com` or `https://<org>.maps.arcgis.com`
- ArcGIS Enterprise: `https://<server>/portal`
- The item URL format is consistent: `{portal_url}/home/item.html?id={item_id}`

**Construct Item URL**:
```python
portal_url = get_portal_url(gis)
item_url = f"{portal_url}/home/item.html?id={new_webmap_id}"
```

### 6. Error Handling

**Potential Issues**:
- Source web map not found
- Permission errors (can't read source or create new)
- Invalid title (special characters, too long)
- Network/API errors
- Missing MAP_SUFFIX setting (should default gracefully)

**Error Messages**:
- Clear, user-friendly error messages
- Log detailed errors for debugging
- Show actionable guidance (e.g., "Check permissions", "Verify web map ID")

### 7. Testing Considerations

**Test Cases**:
1. Copy web map with default title (using MAP_SUFFIX)
2. Copy web map with custom title
3. Copy web map without MAP_SUFFIX set (should use "_Copy" or empty)
4. Handle permission errors gracefully
5. Verify new web map contains all layers and configurations
6. Test portal URL generation for different portal types (AGOL, Enterprise)
7. Test in debug mode (should simulate without creating)

## File Changes Summary

### New Files
- `backend/core/webmap/copy.py` (optional - can add to utils.py instead)
- `docs/IMPLEMENTATION_PLAN_SAVE_AS_NEW_WEBMAP.md` (this file)

### Modified Files
- `backend/core/webmap/utils.py` - Add `copy_webmap_as_new()` function
- `frontend/page_modules/webmap_forms.py` - Add "Save as New" tab
- `frontend/components/common_operations.py` - Add `get_portal_url()` helper (optional)
- `frontend/page_modules/settings.py` - Add MAP_SUFFIX setting (if adding to UI)
- `README.md` - Document MAP_SUFFIX environment variable

### Environment Variables
- `MAP_SUFFIX` - Suffix to append to copied web map titles (default: "_Copy")

## Implementation Order

1. **Phase 1: Backend Function**
   - Implement `copy_webmap_as_new()` in `backend/core/webmap/utils.py`
   - Add `get_portal_url()` helper function
   - Test with debug mode

2. **Phase 2: Settings**
   - Add MAP_SUFFIX to settings UI (optional)
   - Document environment variable
   - Test setting retrieval

3. **Phase 3: Frontend UI**
   - Add "Save as New" tab to webmap_forms.py
   - Implement UI components
   - Add result display with portal link

4. **Phase 4: Testing & Refinement**
   - Test all scenarios
   - Handle edge cases
   - Update documentation

## Example Usage

**With MAP_SUFFIX="_Draft"**:
- Source: "Project Map"
- New: "Project Map_Draft"
- Link: `https://yourorg.maps.arcgis.com/home/item.html?id=abc123`

**With Custom Title**:
- Source: "Project Map"
- Custom: "Project Map - Updated"
- New: "Project Map - Updated"
- Link: `https://yourorg.maps.arcgis.com/home/item.html?id=abc123`

## Future Enhancements

- Batch "Save as New" for multiple web maps
- Copy with options (copy layers, copy forms, copy filters)
- Template-based copying (predefined configurations)
- History tracking of copied maps
