"""
Configuration constants for the Clay GIS Tools application.
Centralizes magic numbers, string constants, and configuration values.
"""

# Web Map Structure Constants
OPERATIONAL_LAYERS_KEY = "operationalLayers"
FORM_INFO_KEY = "formInfo"
FORM_ELEMENTS_KEY = "formElements"
LAYER_DEFINITION_KEY = "layerDefinition"
DEFINITION_EXPRESSION_KEY = "definitionExpression"
EXPRESSION_INFOS_KEY = "expressionInfos"
LAYERS_KEY = "layers"
URL_KEY = "url"
TITLE_KEY = "title"

# Default Values
DEFAULT_GROUP_NAME = "Metadata"
DEFAULT_EXPRESSION_RETURN_TYPE = "string"
DEFAULT_RANDOM_STRING_LENGTH = 8
DEFAULT_EXPRESSION_VALUE_LENGTH = 6

# System Expression Names
EXPR_SYSTEM_FALSE = "expr/system/false"
EXPR_SYSTEM_TRUE = "expr/system/true"

# Limits and Thresholds
MAX_LAYER_SELECTION = 10
MAX_TAG_SEARCH_RESULTS = 50
MAX_BATCH_LAYERS = 10

# Layer Processing
UNNAMED_LAYER = "Unnamed Layer"

# Field Input Type Defaults
DEFAULT_INPUT_TYPE = {
    "type": "text-box",
    "maxLength": 255,
    "minLength": 0
}
