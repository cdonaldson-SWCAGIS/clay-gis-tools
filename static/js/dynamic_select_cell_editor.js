/**
 * Dynamic Select Cell Editor for AgGrid
 * 
 * A custom cell editor that creates a dropdown select element
 * populated with fields from the row's data._fields array.
 * 
 * Supports two field formats:
 * - Legacy: Array of strings ["field1", "field2"]
 * - New: Array of objects [{name: "field1", type: "esriFieldTypeString"}, ...]
 * 
 * Implements the AgGrid ICellEditor interface:
 * - init(params): Initialize the editor with cell parameters
 * - getGui(): Return the DOM element for the editor
 * - getValue(): Return the current value
 * - isCancelBeforeStart(): Whether to cancel editing before it starts
 * - afterGuiAttached(): Called after the GUI is attached to the DOM
 */
class DynamicSelectCellEditor {
    /**
     * Initialize the cell editor
     * @param {Object} params - AgGrid cell editor parameters
     * @param {Object} params.data - Row data containing _fields array
     * @param {string} params.value - Current cell value
     */
    init(params) {
        this.params = params;

        // Try multiple ways to access the row data
        // AgGrid can provide data via params.data or params.node.data
        const rowData = params.data || (params.node && params.node.data) || {};

        // Get the fields array from the row data
        let rawFields = rowData._fields;

        // If _fields is not directly accessible, try to get it from the node
        if (!rawFields && params.node && params.node.data) {
            rawFields = params.node.data._fields;
        }

        // Ensure fields is always an array
        // The fields are stored as a JSON string in the DataFrame to ensure proper serialization
        if (Array.isArray(rawFields)) {
            // Already an array (shouldn't happen with JSON string approach, but handle it)
            this.fields = rawFields;
        } else if (rawFields && typeof rawFields === 'string') {
            // Parse JSON string (expected format from Python)
            try {
                this.fields = JSON.parse(rawFields);
                if (!Array.isArray(this.fields)) {
                    this.fields = [];
                }
            } catch (e) {
                console.warn('DynamicSelectCellEditor: Failed to parse fields JSON string:', e, 'rawFields:', rawFields);
                this.fields = [];
            }
        } else if (rawFields && typeof rawFields === 'object' && rawFields.length !== undefined) {
            // Handle array-like objects (fallback)
            this.fields = Array.from(rawFields);
        } else {
            // Default to empty array
            this.fields = [];
        }

        this.value = params.value || '';

        // Create select element
        this.eSelect = document.createElement('select');
        this.eSelect.style.width = '100%';
        this.eSelect.style.height = '100%';
        this.eSelect.style.border = 'none';
        this.eSelect.style.outline = 'none';

        // Add empty option
        const emptyOption = document.createElement('option');
        emptyOption.value = '';
        emptyOption.text = '';
        this.eSelect.appendChild(emptyOption);

        // Add field options - ensure fields is an array before iterating
        if (Array.isArray(this.fields)) {
            this.fields.forEach((field) => {
                // Handle both string fields and object fields {name, type}
                // This supports both legacy format (strings) and new format (objects)
                let fieldName = null;
                
                if (field != null && typeof field === 'string') {
                    // Legacy format: field is just a string
                    fieldName = field;
                } else if (field != null && typeof field === 'object' && field.name) {
                    // New format: field is an object with name and type properties
                    fieldName = field.name;
                }
                
                if (fieldName != null && typeof fieldName === 'string') {
                    const option = document.createElement('option');
                    option.value = fieldName;
                    option.text = fieldName;
                    if (fieldName === this.value) {
                        option.selected = true;
                    }
                    this.eSelect.appendChild(option);
                }
            });
        }

        // Set initial value
        if (this.value) {
            this.eSelect.value = this.value;
        }
    }

    /**
     * Return the GUI element for this editor
     * @returns {HTMLElement} The select element
     */
    getGui() {
        return this.eSelect;
    }

    /**
     * Get the current value from the editor
     * @returns {string} The selected field name
     */
    getValue() {
        return this.eSelect.value;
    }

    /**
     * Whether to cancel editing before it starts
     * @returns {boolean} Always false
     */
    isCancelBeforeStart() {
        return false;
    }

    /**
     * Called after the GUI is attached to the DOM
     * Focuses the select element for better UX
     */
    afterGuiAttached() {
        if (this.eSelect) {
            this.eSelect.focus();
        }
    }
}
