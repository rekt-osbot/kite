"""
Memory optimization module for Railway deployment.

This module provides functions to optimize memory usage in the application,
especially useful for Railway deployment where memory is limited.
"""
import gc
import sys
import time
import logging
import os
import threading

# Configure logging
logger = logging.getLogger(__name__)

class MemoryOptimizer:
    """
    Memory optimization utility that provides methods to reduce memory usage
    and implements periodic cleanup when running in resource-constrained environments.
    """
    
    def __init__(self, gc_interval=60*30, debug=False):
        """
        Initialize the memory optimizer.
        
        Args:
            gc_interval (int): Interval in seconds for garbage collection (default: 30 minutes)
            debug (bool): Whether to log detailed memory information
        """
        self.gc_interval = gc_interval
        self.debug = debug
        self.last_gc_time = 0
        self.is_running = False
        self.cleanup_thread = None
        
        # Set optimization environment variables
        os.environ['PYTHONUNBUFFERED'] = '1'
        os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
        
        # Check if we're in minimal mode
        self.minimal_mode = os.getenv('MINIMAL_MODE', 'False').lower() == 'true'
        
        if self.minimal_mode:
            logger.info("Running in minimal mode - enabling aggressive memory optimization")
            # Set more aggressive GC in minimal mode
            self.gc_interval = 60 * 15  # 15 minutes
        
        # Initial garbage collection
        self._collect_garbage()
    
    def _collect_garbage(self):
        """Perform garbage collection and log memory statistics"""
        try:
            if self.debug:
                # Log memory statistics before collection
                before_objects = len(gc.get_objects())
            
            # Force garbage collection
            gc.collect()
            
            if self.debug:
                # Log memory statistics after collection
                after_objects = len(gc.get_objects())
                logger.info(f"Memory cleanup: freed {before_objects - after_objects} objects")
                
            self.last_gc_time = time.time()
        except Exception as e:
            logger.error(f"Error during garbage collection: {e}")
    
    def cleanup_unused_modules(self, modules_to_unload=None):
        """
        Unload specified modules to free up memory.
        
        Args:
            modules_to_unload (list): List of module names to unload
        """
        if not modules_to_unload:
            # Default modules that are safe to unload when not in use
            modules_to_unload = [
                'telegram_notifier',
                'nse_holidays',
                'matplotlib',
                'pandas',
                'numpy'
            ]
        
        for module in modules_to_unload:
            if module in sys.modules:
                try:
                    del sys.modules[module]
                    if self.debug:
                        logger.info(f"Unloaded module: {module}")
                except Exception as e:
                    logger.error(f"Error unloading module {module}: {e}")
        
        # Run garbage collection after unloading modules
        gc.collect()
    
    def optimize_dict(self, d):
        """
        Optimize a dictionary by removing None values and empty containers.
        
        Args:
            d (dict): Dictionary to optimize
            
        Returns:
            dict: Optimized dictionary
        """
        if not isinstance(d, dict):
            return d
            
        # Create a new dict with only non-None and non-empty values
        return {
            k: self.optimize_dict(v) if isinstance(v, dict) else v
            for k, v in d.items()
            if v is not None and (not hasattr(v, '__len__') or len(v) > 0)
        }
    
    def periodic_cleanup(self):
        """Background thread function for periodic memory cleanup"""
        while self.is_running:
            try:
                current_time = time.time()
                
                # Run garbage collection periodically
                if current_time - self.last_gc_time > self.gc_interval:
                    self._collect_garbage()
                
                # Sleep for a short interval to reduce CPU usage
                # Use multiple short sleeps instead of one long sleep to allow clean shutdown
                for _ in range(60):
                    if not self.is_running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in memory optimization thread: {e}")
                # Don't stop the thread on error
                time.sleep(60)
    
    def start_periodic_cleanup(self):
        """Start the background cleanup thread"""
        if not self.is_running:
            self.is_running = True
            self.cleanup_thread = threading.Thread(
                target=self.periodic_cleanup,
                daemon=True
            )
            self.cleanup_thread.start()
            logger.info(f"Started memory optimization thread (interval: {self.gc_interval}s)")
    
    def stop_periodic_cleanup(self):
        """Stop the background cleanup thread"""
        self.is_running = False
        if self.cleanup_thread:
            # No need to join the thread as it's daemonized
            logger.info("Stopped memory optimization thread")

# Global instance
memory_optimizer = MemoryOptimizer()

def start_optimization():
    """Start the memory optimization background thread"""
    memory_optimizer.start_periodic_cleanup()

def stop_optimization():
    """Stop the memory optimization background thread"""
    memory_optimizer.stop_periodic_cleanup()

def cleanup_modules(modules=None):
    """
    Clean up specified modules to free memory.
    Args:
        modules (list): List of module names to unload
    """
    memory_optimizer.cleanup_unused_modules(modules)

def optimize_dict(d):
    """
    Optimize a dictionary by removing None values and empty containers.
    
    Args:
        d (dict): Dictionary to optimize
        
    Returns:
        dict: Optimized dictionary
    """
    return memory_optimizer.optimize_dict(d)

# Initialize the memory optimization on import, but don't start the thread
# Call start_optimization() explicitly in your main module
if __name__ == "__main__":
    # If run directly, perform a single optimization pass
    print("Performing memory optimization...")
    memory_optimizer._collect_garbage()
    print("Memory optimization complete!") 