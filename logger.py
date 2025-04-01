"""
Centralized logging configuration for the entire application.
This module provides a consistent logging setup and should be imported
by other modules that need logging.
"""

import logging
import sys
import time

# Dictionary to track recent log messages to prevent duplicates
_recent_logs = {}
_LOG_TIMEOUT = 1  # seconds to consider logs as duplicates

class DuplicateFilter(logging.Filter):
    """Filter to prevent duplicate log messages within a short time window"""
    
    def filter(self, record):
        # Create a key from the log message and level
        key = (record.getMessage(), record.levelno)
        
        # Get current time
        now = time.time()
        
        # Check if we've seen this message recently
        last_time = _recent_logs.get(key)
        if last_time and now - last_time < _LOG_TIMEOUT:
            # It's a duplicate within our time window, so filter it out
            return False
        
        # It's a new message or outside the time window, so update and accept it
        _recent_logs[key] = now
        
        # Clean up old messages from the cache
        for old_key in list(_recent_logs.keys()):
            if now - _recent_logs[old_key] > _LOG_TIMEOUT * 10:  # Keep cache manageable
                del _recent_logs[old_key]
        
        return True

def setup_logging():
    """
    Configure logging for the entire application.
    Should be called once at application startup.
    """
    # Configure the root logger only if it hasn't been already
    if not logging.getLogger().handlers:
        # Create handler
        console_handler = logging.StreamHandler(sys.stdout)
        
        # Create formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)
        
        # Add duplicate filter
        duplicate_filter = DuplicateFilter()
        console_handler.addFilter(duplicate_filter)
        
        # Set up root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(console_handler)
        
        logging.info("Centralized logging system initialized")

def get_logger(name):
    """
    Get a properly configured logger for the specified module.
    
    Args:
        name (str): The name of the module (usually __name__)
        
    Returns:
        logging.Logger: A configured logger instance
    """
    return logging.getLogger(name)

# Setup logging when the module is imported
setup_logging() 