"""Centralized configuration for dv-smith."""

import logging
import os


def setup_logging() -> logging.Logger:
    """Configure and return the root logger for dv-smith.
    
    Returns:
        Configured logger instance
    """
    # Determine log level based on DVSMITH_DEBUG environment variable
    debug_enabled = os.getenv("DVSMITH_DEBUG", "").lower() in ("1", "true", "yes")
    log_level = logging.DEBUG if debug_enabled else logging.INFO
    
    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='[%(levelname)s] %(message)s'
    )
    
    return logging.getLogger("dvsmith")


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module.
    
    Args:
        name: Module name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(f"dvsmith.{name}")


# Initialize logging on module import
_root_logger = setup_logging()
