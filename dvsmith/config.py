"""Centralized configuration for dv-smith."""

import logging
import os
import sys


class TqdmLoggingHandler(logging.Handler):
    """Custom logging handler that works with tqdm progress bars."""
    
    def emit(self, record):
        try:
            from tqdm import tqdm
            msg = self.format(record)
            tqdm.write(msg, file=sys.stderr)
        except Exception:
            self.handleError(record)


def setup_logging() -> logging.Logger:
    """Configure and return the root logger for dv-smith.
    
    Returns:
        Configured logger instance
    """
    # Determine log level based on DVSMITH_DEBUG environment variable
    debug_enabled = os.getenv("DVSMITH_DEBUG", "").lower() in ("1", "true", "yes")
    log_level = logging.DEBUG if debug_enabled else logging.INFO
    
    # Create root logger
    logger = logging.getLogger("dvsmith")
    logger.setLevel(log_level)
    
    # Remove any existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Add tqdm-compatible handler
    handler = TqdmLoggingHandler()
    handler.setLevel(log_level)
    formatter = logging.Formatter('[%(levelname)s] %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Allow propagation for testing (pytest caplog needs this)
    logger.propagate = True
    
    return logger


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
