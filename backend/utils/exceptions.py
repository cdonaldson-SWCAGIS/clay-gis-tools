"""
Custom exception classes for the Clay GIS Tools application.
Provides consistent error handling across all modules.
"""


class ClayGISError(Exception):
    """Base exception for all Clay GIS Tools errors."""
    pass


class AuthenticationError(ClayGISError):
    """Raised when authentication fails or credentials are missing."""
    pass


class WebMapError(ClayGISError):
    """Base exception for web map operations."""
    pass


class WebMapNotFoundError(WebMapError):
    """Raised when a web map cannot be found."""
    pass


class InvalidWebMapError(WebMapError):
    """Raised when a web map is invalid or inaccessible."""
    pass


class LayerProcessingError(WebMapError):
    """Raised when layer processing fails."""
    pass


class LayerNotFoundError(WebMapError):
    """Raised when a specific layer cannot be found in a web map."""
    pass


class ConfigurationError(ClayGISError):
    """Raised when there is a configuration error."""
    pass


class ValidationError(ClayGISError):
    """Raised when input validation fails."""
    pass


class OperationError(ClayGISError):
    """Raised when an operation fails."""
    pass
