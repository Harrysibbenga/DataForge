"""
tests/run_tests.py - Test runner for DataForge
"""
import unittest
import sys
import os

# Add the parent directory to sys.path to ensure imports work correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

if __name__ == '__main__':
    # Discover and run all tests
    test_loader = unittest.TestLoader()
    
    # Find all test files in the 'tests' directory
    test_dir = os.path.dirname(os.path.abspath(__file__))
    test_suite = test_loader.discover(test_dir, pattern='test_*.py')
    
    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    result = test_runner.run(test_suite)
    
    # Return non-zero exit code if tests failed
    sys.exit(not result.wasSuccessful())