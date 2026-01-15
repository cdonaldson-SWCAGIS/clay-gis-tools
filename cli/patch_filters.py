#!/usr/bin/env python3
"""
CLI wrapper for updating web map filters.
Thin wrapper around backend.core.webmap.filters
"""

import sys
import argparse
import logging

from backend.utils.auth import authenticate_from_env
from backend.utils.exceptions import AuthenticationError
from backend.utils.logging import get_logger, configure_logging
from backend.core.webmap.filters import update_webmap_definition_by_field

logger = get_logger("cli.patch_filters")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Update definition expressions (filters) in ArcGIS web maps"
    )
    parser.add_argument(
        "--webmap_id",
        required=True,
        help="Web map item ID"
    )
    parser.add_argument(
        "--field",
        required=True,
        help="Target field name"
    )
    parser.add_argument(
        "--filter",
        required=True,
        help="New filter expression (SQL WHERE clause)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (simulate updates without saving)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    configure_logging(level=log_level)
    
    # Authenticate
    try:
        gis = authenticate_from_env()
    except (ValueError, AuthenticationError) as e:
        logger.error(f"Authentication failed: {e}")
        logger.error("Please set ARCGIS_USERNAME and ARCGIS_PASSWORD environment variables")
        sys.exit(1)
    
    # Perform update
    updated_layers = update_webmap_definition_by_field(
        args.webmap_id,
        args.field,
        args.filter,
        gis,
        debug_mode=args.debug
    )
    
    # Print results
    print("---")
    if updated_layers:
        print(f"Successfully updated {len(updated_layers)} layers")
        
        if args.debug:
            print("Note: Running in DEBUG mode - changes were simulated and not saved to the server")
        else:
            print("Changes were verified and saved to the server")
    else:
        print("No layers were updated")
        
        if not args.debug:
            print("Possible issues:")
            print("  • The web map may not contain layers with the target field")
            print("  • The server may not have accepted the changes")
            print("  • There might be permission issues with the web map")
            print("\nTry running with --debug to see more details")
    
    sys.exit(0 if updated_layers else 1)


if __name__ == "__main__":
    main()
