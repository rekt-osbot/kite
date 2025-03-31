#!/usr/bin/env python
"""
Module to demonstrate how to resolve circular import dependencies.
This is a proof of concept before modifying the main codebase.
"""
import logging
import importlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def lazy_import(module_name, class_name=None):
    """
    Create a lazy importer that only imports the module when first accessed.
    This helps break circular dependencies by delaying imports until actually needed.
    
    Args:
        module_name (str): The module to import
        class_name (str, optional): Specific class to import from the module
        
    Returns:
        object: A proxy object that loads the module/class on first access
    """
    class LazyImporter:
        def __init__(self):
            self._module = None
            self._class = None
        
        def __getattr__(self, name):
            if self._module is None:
                logger.debug(f"Lazy-loading module {module_name}")
                self._module = importlib.import_module(module_name)
                
                if class_name:
                    logger.debug(f"Lazy-loading class {class_name} from {module_name}")
                    self._class = getattr(self._module, class_name)
                    return getattr(self._class, name)
                
            return getattr(self._module, name)
        
        def __call__(self, *args, **kwargs):
            if self._module is None:
                logger.debug(f"Lazy-loading module {module_name}")
                self._module = importlib.import_module(module_name)
                
                if class_name:
                    logger.debug(f"Lazy-loading class {class_name} from {module_name}")
                    self._class = getattr(self._module, class_name)
                    return self._class(*args, **kwargs)
                
            return self._module(*args, **kwargs)
    
    return LazyImporter()

# Example usage of how to reorganize code to avoid circular dependencies:

# 1. Create stub files for demonstration
def create_demo_files():
    """Create demo files to demonstrate circular dependency resolution"""
    # Module A (originally depends on B)
    with open('demo_module_a.py', 'w') as f:
        f.write("""
# Original approach with circular dependency issue
# import demo_module_b  # This would cause a circular dependency

# Instead, use lazy imports or local imports
from dependency_resolver import lazy_import

# Lazy import that only loads when used
module_b = lazy_import('demo_module_b')

class ClassA:
    def __init__(self):
        self.name = "ClassA"
    
    def get_name(self):
        return self.name
    
    def use_b(self):
        # Only import B when actually needed
        # Method 1: Using lazy import defined above
        return module_b.ClassB().get_name()
        
        # Method 2: Alternative using local import
        # from demo_module_b import ClassB
        # return ClassB().get_name()

def function_in_a():
    return "Function in A"
""")

    # Module B (originally depends on A)
    with open('demo_module_b.py', 'w') as f:
        f.write("""
# Original approach with circular dependency issue
# import demo_module_a  # This would cause a circular dependency

# Instead, use function-level imports
class ClassB:
    def __init__(self):
        self.name = "ClassB"
    
    def get_name(self):
        return self.name
    
    def use_a(self):
        # Only import A when actually needed
        # Function-level import to avoid circular dependency
        from demo_module_a import ClassA
        return ClassA().get_name()

def function_in_b():
    # Import only when needed
    from demo_module_a import function_in_a
    return f"Function in B, calling: {function_in_a()}"
""")

    # Main module to test
    with open('demo_main.py', 'w') as f:
        f.write("""
# Import both modules without circular dependency issues
from demo_module_a import ClassA
from demo_module_b import ClassB

def main():
    a = ClassA()
    b = ClassB()
    
    print(f"From A: {a.get_name()}")
    print(f"From B: {b.get_name()}")
    
    print(f"A using B: {a.use_b()}")
    print(f"B using A: {b.use_a()}")
    
    from demo_module_b import function_in_b
    print(function_in_b())

if __name__ == "__main__":
    main()
""")


def test_lazy_imports():
    """Test the lazy import functionality"""
    # Create an example lazy import
    logging_module = lazy_import('logging')
    
    # Using it should trigger the import
    logger = logging_module.getLogger("test_logger")
    logger.setLevel(logging_module.INFO)
    
    print("Successfully created logger with lazy import")


if __name__ == "__main__":
    logger.info("Starting dependency resolver test...")
    
    # Test lazy imports
    test_lazy_imports()
    
    # Create demo files to show circular dependency resolution
    create_demo_files()
    logger.info("Created demo files for circular dependency resolution")
    logger.info("You can run them with: python demo_main.py")
    
    # Try running the demo
    try:
        logger.info("Running demo_main.py:")
        print("-" * 50)
        import demo_main
        demo_main.main()
        print("-" * 50)
    except Exception as e:
        logger.error(f"Error running demo: {e}")
    
    logger.info("Dependency resolver test completed") 