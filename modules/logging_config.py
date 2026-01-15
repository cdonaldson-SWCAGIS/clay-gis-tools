"""
Centralized logging configuration for the Clay GIS Tools application.
Configures logging once at application startup.
"""

import logging
import sys
from typing import Optional


def configure_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    date_format: Optional[str] = None
) -> None:
    """
    Configure logging for the application.
    Should be called once at application startup.
    
    Args:
        level: Logging level (default: INFO)
        format_string: Custom format string (optional)
        date_format: Custom date format (optional)
    """
    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    if date_format is None:
        date_format = "%Y-%m-%d %H:%M:%S"
    
    # Only configure if not already configured
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=level,
            format=format_string,
            datefmt=date_format,
            stream=sys.stdout,
            force=True
        )


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a module.
    Use this instead of logging.getLogger() to ensure consistent configuration.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
