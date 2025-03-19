"""
tests/test_api.py - Tests for the DataForge API routes
"""
import unittest
from fastapi.testclient import TestClient
import pandas as pd
import io
import os
import json
from app.api.routes import app

class TestAPI(unittest.TestCase):
    """Test cases for API endpoints"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.client = TestClient(app)
        
        # Create a sample CSV file for testing
        self.sample_data = pd.DataFrame({
            'name': ['John Doe', 'Jane Smith', 'Bob Johnson'],
            'age': [30, 25, 40],
            'city': ['New York', 'London', 'Paris']
        })
        
        # Save as a temporary CSV file
        self.csv_path = 'test_data.csv'
        self.sample_data.to_csv(self.csv_path, index=False)
    
    def tearDown(self):
        """Clean up test fixtures"""
        # Remove temporary file
        if os.path.exists(self.csv_path):
            os.remove(self.csv_path)
    
    def test_index_route(self):
        """Test the main page route"""
        response = self.client.get("/")
        
        # Check status code and content type
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/html; charset=utf-8")
    
    def test_formats_route(self):
        """Test the formats API endpoint"""
        response = self.client.get("/api/formats")
        
        # Check status code
        self.assertEqual(response.status_code, 200)
        
        # Parse response
        data = response.json()
        
        # Check that formats are returned
        self.assertIn("formats", data)
        self.assertIsInstance(data["formats"], list)
        
        # Check that expected formats are present
        expected_formats = ['csv', 'json', 'excel', 'xml', 'yaml']
        for fmt in expected_formats:
            self.assertIn(fmt, data["formats"])
    
    def test_convert_csv_to_json(self):
        """Test converting CSV to JSON"""
        # Create file data
        with open(self.csv_path, 'rb') as f:
            file_content = f.read()
        
        # Make request
        response = self.client.post(
            "/api/convert",
            files={"file": ("test_data.csv", file_content, "text/csv")},
            data={
                "to_format": "json",
                "remove_empty_rows_flag": "false",
                "remove_empty_cols_flag": "false",
                "standardize_names_flag": "false",
                "trim_whitespace_flag": "false",
                "deduplicate_flag": "false"
            }
        )
        
        # Check status code
        self.assertEqual(response.status_code, 200)
        
        # Parse response
        result_data = json.loads(response.content)
        
        # Check that data was converted correctly
        self.assertEqual(len(result_data), 3)
        self.assertEqual(result_data[0]["name"], "John Doe")
        self.assertEqual(result_data[1]["age"], 25)
        self.assertEqual(result_data[2]["city"], "Paris")
    
    def test_convert_with_transformations(self):
        """Test converting with transformations applied"""
        # Create a sample CSV with duplicate rows and whitespace
        test_data = pd.DataFrame({
            'name': ['  John ', 'Jane  ', '  John '],
            'age': [30, 25, 30],
            'city': ['New York  ', '  London', 'New York  ']
        })
        
        test_csv_path = 'test_transform.csv'
        test_data.to_csv(test_csv_path, index=False)
        
        try:
            # Read file content
            with open(test_csv_path, 'rb') as f:
                file_content = f.read()
            
            # Make request with transformations
            response = self.client.post(
                "/api/convert",
                files={"file": ("test_transform.csv", file_content, "text/csv")},
                data={
                    "to_format": "json",
                    "remove_empty_rows_flag": "true",
                    "remove_empty_cols_flag": "true",
                    "standardize_names_flag": "true",
                    "trim_whitespace_flag": "true",
                    "deduplicate_flag": "true"
                }
            )
            
            # Check status code
            self.assertEqual(response.status_code, 200)
            
            # Parse response
            result_data = json.loads(response.content)
            
            # Check that transformations were applied
            # Should have 2 rows (after deduplication)
            self.assertEqual(len(result_data), 2)
            
            # Names should be trimmed
            self.assertEqual(result_data[0]["name"], "John")
            self.assertEqual(result_data[1]["name"], "Jane")
            
            # Column names should be standardized
            for item in result_data:
                self.assertTrue(all(key.islower() for key in item.keys()))
        
        finally:
            # Clean up
            if os.path.exists(test_csv_path):
                os.remove(test_csv_path)
    
    def test_convert_invalid_format(self):
        """Test handling of invalid format requests"""
        # Create file data
        with open(self.csv_path, 'rb') as f:
            file_content = f.read()
        
        # Make request with invalid format
        response = self.client.post(
            "/api/convert",
            files={"file": ("test_data.csv", file_content, "text/csv")},
            data={"to_format": "invalid_format"}
        )
        
        # Should return 400 Bad Request
        self.assertEqual(response.status_code, 400)
        
        # Check error message
        data = response.json()
        self.assertIn("detail", data)
        self.assertIn("Unsupported target format", data["detail"])

if __name__ == '__main__':
    unittest.main()
