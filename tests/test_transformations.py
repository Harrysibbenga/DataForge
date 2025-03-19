"""
tests/test_transformations.py - Tests for the DataForge transformations module
"""
import unittest
import pandas as pd
import numpy as np
from app.core.transformations import (
    remove_empty_rows,
    remove_empty_columns,
    rename_columns,
    convert_column_types,
    trim_whitespace,
    filter_rows,
    standardize_column_names,
    deduplicate_rows,
    impute_missing_values,
    create_transformation_pipeline
)

class TestTransformations(unittest.TestCase):
    """Test cases for data transformation functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        # DataFrame with empty rows and columns
        self.df_with_empty = pd.DataFrame({
            'A': [1, 2, np.nan, 4],
            'B': [5, 6, np.nan, 8],
            'C': [np.nan, np.nan, np.nan, np.nan],
            'D': ['a', 'b', np.nan, '']
        })
        
        # DataFrame with whitespace in text
        self.df_with_whitespace = pd.DataFrame({
            'name': ['  John ', 'Jane  ', ' Bob'],
            'city': ['New York  ', '  London', 'Paris ']
        })
        
        # DataFrame with duplicate rows
        self.df_with_duplicates = pd.DataFrame({
            'name': ['John', 'Jane', 'John', 'Bob'],
            'age': [30, 25, 30, 40]
        })
        
        # DataFrame with inconsistent column names
        self.df_bad_columns = pd.DataFrame({
            'First Name': ['John', 'Jane', 'Bob'],
            'Last-Name': ['Doe', 'Smith', 'Johnson'],
            '123Age': [30, 25, 40]
        })
        
        # DataFrame with missing values
        self.df_missing = pd.DataFrame({
            'numeric': [1, 2, np.nan, 4, 5],
            'categorical': ['A', 'B', np.nan, 'D', 'E']
        })
    
    def test_remove_empty_rows(self):
        """Test removing empty rows"""
        result = remove_empty_rows(self.df_with_empty)
        
        # Should have 3 rows (the row with only NaN values should be removed)
        self.assertEqual(len(result), 3)
        
        # Check that row indices are reset
        self.assertEqual(list(result.index), [0, 1, 2])
    
    def test_remove_empty_columns(self):
        """Test removing empty columns"""
        result = remove_empty_columns(self.df_with_empty)
        
        # Should have 3 columns (column C should be removed)
        self.assertEqual(len(result.columns), 3)
        self.assertNotIn('C', result.columns)
    
    def test_rename_columns(self):
        """Test renaming columns"""
        mapping = {'A': 'Alpha', 'B': 'Beta'}
        result = rename_columns(self.df_with_empty, mapping)
        
        # Check that columns are renamed
        self.assertIn('Alpha', result.columns)
        self.assertIn('Beta', result.columns)
        self.assertNotIn('A', result.columns)
        self.assertNotIn('B', result.columns)
    
    def test_convert_column_types(self):
        """Test converting column types"""
        df = pd.DataFrame({
            'string_col': ['1', '2', '3'],
            'float_col': ['1.1', '2.2', '3.3']
        })
        
        type_mapping = {
            'string_col': 'int',
            'float_col': 'float'
        }
        
        result = convert_column_types(df, type_mapping)
        
        # Check column types
        self.assertEqual(result['string_col'].dtype, 'int64')
        self.assertEqual(result['float_col'].dtype, 'float64')
    
    def test_trim_whitespace(self):
        """Test trimming whitespace"""
        result = trim_whitespace(self.df_with_whitespace)
        
        # Check that whitespace is trimmed
        self.assertEqual(result['name'][0], 'John')
        self.assertEqual(result['name'][1], 'Jane')
        self.assertEqual(result['name'][2], 'Bob')
        self.assertEqual(result['city'][0], 'New York')
        self.assertEqual(result['city'][1], 'London')
        self.assertEqual(result['city'][2], 'Paris')
    
    def test_filter_rows(self):
        """Test filtering rows"""
        # Define condition: age > 25
        condition = lambda row: row['age'] > 25
        
        result = filter_rows(self.df_with_duplicates, condition)
        
        # Should have 3 rows (2 with John, age 30 and 1 with Bob, age 40)
        self.assertEqual(len(result), 3)
        
        # All rows should have age > 25
        self.assertTrue(all(result['age'] > 25))
    
    def test_standardize_column_names(self):
        """Test standardizing column names"""
        result = standardize_column_names(self.df_bad_columns)
        
        # Check that column names are standardized
        column_list = list(result.columns)
        self.assertIn('first_name', column_list)
        self.assertIn('last_name', column_list)
        self.assertIn('col_123age', column_list)
    
    def test_deduplicate_rows(self):
        """Test removing duplicate rows"""
        result = deduplicate_rows(self.df_with_duplicates)
        
        # Should have 3 unique rows
        self.assertEqual(len(result), 3)
        
        # Check specific rows exist
        self.assertTrue(any((result['name'] == 'John') & (result['age'] == 30)))
        self.assertTrue(any((result['name'] == 'Jane') & (result['age'] == 25)))
        self.assertTrue(any((result['name'] == 'Bob') & (result['age'] == 40)))
    
    def test_impute_missing_values(self):
        """Test imputing missing values"""
        strategy = {
            'numeric': 'mean',
            'categorical': 'value:Unknown'
        }
        
        result = impute_missing_values(self.df_missing, strategy)
        
        # Check that missing values are filled
        self.assertFalse(result['numeric'].isna().any())
        self.assertFalse(result['categorical'].isna().any())
        
        # Check the imputed values
        mean_value = self.df_missing['numeric'].mean()
        self.assertEqual(result['numeric'][2], mean_value)
        self.assertEqual(result['categorical'][2], 'Unknown')
    
    def test_transformation_pipeline(self):
        """Test creating and applying a transformation pipeline"""
        # Create a pipeline with multiple transformations
        pipeline = create_transformation_pipeline([
            remove_empty_columns,
            remove_empty_rows,
            lambda df: trim_whitespace(df)
        ])
        
        # Test data with empty rows, columns, and whitespace
        test_df = pd.DataFrame({
            'A': [1, 2, np.nan, 4],
            'B': [' x ', ' y ', np.nan, ' w '],  # Using NaN instead of empty string
            'C': [np.nan, np.nan, np.nan, np.nan]
        })
        
        # Create an explicitly empty row
        test_df.loc[2, :] = np.nan
        
        result = pipeline(test_df)
        
        # Should have 3 rows (row with all NaN removed)
        self.assertEqual(len(result), 3)
        
        # Should have 2 columns (empty column C removed)
        self.assertEqual(len(result.columns), 2)
        
        # Whitespace should be trimmed
        self.assertEqual(result['B'][0], 'x')
        self.assertEqual(result['B'][1], 'y')
        self.assertEqual(result['B'][2], 'w')

if __name__ == '__main__':
    unittest.main()