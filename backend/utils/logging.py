"""
Centralized logging configuration
Configures logging once at application startup using Rich.
"""

import logging
import sys

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install as install_rich_traceback


def configure_logging(
    level: int = logging.INFO,
    rich_tracebacks: bool = True,
    show_time: bool = True,
    show_path: bool = True,
    markup: bool = True
) -> None:
    """
    Configure logging for the application using Rich.
    Should be called once at application startup.
    
    Args:
        level: Logging level (default: INFO)
        rich_tracebacks: Enable rich traceback formatting (default: True)
        show_time: Show timestamps in log messages (default: True)
        show_path: Show file path in log messages (default: True)
        markup: Enable rich markup in log messages (default: True)
    """
    # Only configure if not already configured
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return
    
    # Install rich traceback handler for better exception formatting
    if rich_tracebacks:
        install_rich_traceback(
            show_locals=False,  # Set to True for debugging if needed
            suppress=[logging]  # Suppress traceback frames from logging module
        )
    
    # Create console for rich output
    console = Console(
        file=sys.stdout,
        force_terminal=True,  # Force terminal mode even if not detected
        width=None  # Auto-detect width
    )
    
    # Create rich handler with sensible defaults
    rich_handler = RichHandler(
        console=console,
        show_time=show_time,
        show_path=show_path,
        markup=markup,
        rich_tracebacks=rich_tracebacks,
        tracebacks_show_locals=False,  # Set to True for debugging if needed
        show_level=True
    )
    rich_handler.setLevel(level)
    
    # Configure root logger
    root_logger.setLevel(level)
    root_logger.addHandler(rich_handler)


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
