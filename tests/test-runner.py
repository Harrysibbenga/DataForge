"""
tests/run_tests.py - Run all DataForge tests
"""
import unittest
import sys
import os

# Add the parent directory to the path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import test modules
from tests.test_converter import TestDataConverter
from tests.test_transformations import TestTransformations
from tests.test_api import TestAPI

if __name__ == '__main__':
    # Create the test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestDataConverter))
    suite.addTests(loader.loadTestsFromTestCase(TestTransformations))
    suite.addTests(loader.loadTestsFromTestCase(TestAPI))
    
    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(not result.wasSuccessful())
