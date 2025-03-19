"""
tests/test_converter.py - Tests for the DataForge converter module
"""
import unittest
import pandas as pd
import io
import json
import yaml
from app.core.converter import DataConverter

class TestDataConverter(unittest.TestCase):
    """Test cases for DataConverter class"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.converter = DataConverter()
        
        # Create sample data
        self.sample_data = pd.DataFrame({
            'name': ['John', 'Jane', 'Bob'],
            'age': [30, 25, 40],
            'city': ['New York', 'London', 'Paris']
        })
        
        # Create sample data in different formats
        self.csv_data = self.sample_data.to_csv(index=False)
        self.json_data = self.sample_data.to_json(orient='records')
        
        # Create XML manually since pandas doesn't have direct XML conversion
        self.xml_data = """
        <data>
            <record>
                <name>John</name>
                <age>30</age>
                <city>New York</city>
            </record>
            <record>
                <name>Jane</name>
                <age>25</age>
                <city>London</city>
            </record>
            <record>
                <name>Bob</name>
                <age>40</age>
                <city>Paris</city>
            </record>
        </data>
        """
        
        # Create YAML data
        self.yaml_data = yaml.dump(
            self.sample_data.to_dict(orient='records'),
            sort_keys=False
        )
    
    def test_detect_format(self):
        """Test format detection from filename"""
        self.assertEqual(self.converter.detect_format('data.csv'), 'csv')
        self.assertEqual(self.converter.detect_format('data.json'), 'json')
        self.assertEqual(self.converter.detect_format('data.xlsx'), 'excel')
        self.assertEqual(self.converter.detect_format('data.xml'), 'xml')
        self.assertEqual(self.converter.detect_format('data.yaml'), 'yaml')
        self.assertEqual(self.converter.detect_format('data.yml'), 'yaml')
        
        # Test with uppercase extension
        self.assertEqual(self.converter.detect_format('data.CSV'), 'csv')
        
        # Test with invalid extension
        with self.assertRaises(ValueError):
            self.converter.detect_format('data.invalid')
    
    def test_csv_to_json(self):
        """Test conversion from CSV to JSON"""
        result = self.converter.convert(self.csv_data, 'csv', 'json')
        
        # Parse the result to compare data
        result_data = json.loads(result)
        
        # Check if the data structure matches
        self.assertEqual(len(result_data), 3)
        self.assertEqual(result_data[0]['name'], 'John')
        self.assertEqual(result_data[1]['age'], 25)
        self.assertEqual(result_data[2]['city'], 'Paris')
    
    def test_json_to_csv(self):
        """Test conversion from JSON to CSV"""
        result = self.converter.convert(self.json_data, 'json', 'csv')
        
        # Convert result back to DataFrame for comparison
        result_df = pd.read_csv(io.StringIO(result))
        
        # Check if the data structure matches
        self.assertEqual(len(result_df), 3)
        self.assertEqual(result_df.iloc[0]['name'], 'John')
        self.assertEqual(result_df.iloc[1]['age'], 25)
        self.assertEqual(result_df.iloc[2]['city'], 'Paris')
    
    def test_xml_conversion(self):
        """Test XML conversions"""
        # XML to JSON
        result = self.converter.convert(self.xml_data, 'xml', 'json')
        result_data = json.loads(result)
        
        # Basic validation
        self.assertEqual(len(result_data), 3)
        self.assertTrue('name' in result_data[0])
        self.assertTrue('age' in result_data[0])
        self.assertTrue('city' in result_data[0])
    
    def test_yaml_conversion(self):
        """Test YAML conversions"""
        # YAML to JSON
        result = self.converter.convert(self.yaml_data, 'yaml', 'json')
        result_data = json.loads(result)
        
        # Basic validation
        self.assertEqual(len(result_data), 3)
        self.assertEqual(result_data[0]['name'], 'John')
        self.assertEqual(result_data[1]['age'], 25)
        self.assertEqual(result_data[2]['city'], 'Paris')
    
    def test_invalid_format(self):
        """Test handling of invalid formats"""
        with self.assertRaises(ValueError):
            self.converter.convert(self.csv_data, 'invalid', 'json')
        
        with self.assertRaises(ValueError):
            self.converter.convert(self.csv_data, 'csv', 'invalid')

if __name__ == '__main__':
    unittest.main()