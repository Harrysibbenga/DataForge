"""
core/converter.py - Core conversion functionality
"""
import pandas as pd
import json
import yaml
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Union, Callable
import io
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DataConverter:
    """Core data conversion engine that handles transformations between formats"""
    
    # Define supported formats and their file extensions
    SUPPORTED_FORMATS = {
        'csv': ['.csv'],
        'json': ['.json'],
        'excel': ['.xlsx', '.xls'],
        'xml': ['.xml'],
        'yaml': ['.yaml', '.yml']
    }
    
    def __init__(self):
        """Initialize the converter with handlers for different formats"""
        # Register readers (format -> handler function)
        self.readers = {
            'csv': self._read_csv,
            'json': self._read_json,
            'excel': self._read_excel,
            'xml': self._read_xml,
            'yaml': self._read_yaml
        }
        
        # Register writers (format -> handler function)
        self.writers = {
            'csv': self._write_csv,
            'json': self._write_json,
            'excel': self._write_excel,
            'xml': self._write_xml,
            'yaml': self._write_yaml
        }
    
    def detect_format(self, filename: str) -> str:
        """Detect format from filename extension"""
        extension = '.' + filename.split('.')[-1].lower()
        
        for format_name, extensions in self.SUPPORTED_FORMATS.items():
            if extension in extensions:
                return format_name
        
        raise ValueError(f"Unsupported file extension: {extension}")
    
    def convert(self, 
                input_data: Union[str, bytes, io.IOBase], 
                from_format: str, 
                to_format: str,
                transformations: List[Callable] = None) -> Union[str, bytes]:
        """
        Convert data from one format to another with optional transformations
        
        Args:
            input_data: The input data as string, bytes or file-like object
            from_format: Source format (csv, json, excel, xml, yaml)
            to_format: Target format (csv, json, excel, xml, yaml)
            transformations: List of functions to apply to the data during conversion
            
        Returns:
            Converted data in the target format
        """
        # Validate formats
        if from_format not in self.readers:
            raise ValueError(f"Unsupported source format: {from_format}")
        if to_format not in self.writers:
            raise ValueError(f"Unsupported target format: {to_format}")
            
        # Read data into a pandas DataFrame
        logger.info(f"Reading data from {from_format} format")
        df = self.readers[from_format](input_data)
        
        # Apply transformations if provided
        if transformations:
            logger.info(f"Applying {len(transformations)} transformations")
            for transform_func in transformations:
                df = transform_func(df)
        
        # Write data to target format
        logger.info(f"Converting data to {to_format} format")
        return self.writers[to_format](df)
    
    # Reader methods
    def _read_csv(self, input_data: Union[str, bytes, io.IOBase]) -> pd.DataFrame:
        """Read CSV data into DataFrame"""
        if isinstance(input_data, str):
            return pd.read_csv(io.StringIO(input_data))
        elif isinstance(input_data, bytes):
            return pd.read_csv(io.BytesIO(input_data))
        else:
            return pd.read_csv(input_data)
    
    def _read_json(self, input_data: Union[str, bytes, io.IOBase]) -> pd.DataFrame:
        """Read JSON data into DataFrame"""
        return pd.read_json(input_data)
    
    def _read_excel(self, input_data: Union[str, bytes, io.IOBase]) -> pd.DataFrame:
        """Read Excel data into DataFrame"""
        return pd.read_excel(input_data)
    
    def _read_xml(self, input_data: Union[str, bytes, io.IOBase]) -> pd.DataFrame:
        """Read XML data into DataFrame"""
        if isinstance(input_data, str):
            root = ET.fromstring(input_data)
        elif isinstance(input_data, bytes):
            root = ET.fromstring(input_data.decode('utf-8'))
        else:
            tree = ET.parse(input_data)
            root = tree.getroot()
        
        # Simple XML to DataFrame conversion
        # This handles flat, regular XML structures
        data = []
        for child in root:
            row = {}
            for element in child:
                row[element.tag] = element.text
            data.append(row)
        
        return pd.DataFrame(data)
    
    def _read_yaml(self, input_data: Union[str, bytes, io.IOBase]) -> pd.DataFrame:
        """Read YAML data into DataFrame"""
        if isinstance(input_data, (str, bytes)):
            data = yaml.safe_load(input_data)
        else:
            data = yaml.safe_load(input_data.read())
        
        return pd.DataFrame(data)
    
    # Writer methods
    def _write_csv(self, df: pd.DataFrame) -> str:
        """Convert DataFrame to CSV string"""
        return df.to_csv(index=False)
    
    def _write_json(self, df: pd.DataFrame) -> str:
        """Convert DataFrame to JSON string"""
        return df.to_json(orient='records')
    
    def _write_excel(self, df: pd.DataFrame) -> bytes:
        """Convert DataFrame to Excel bytes"""
        output = io.BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)
        return output.getvalue()
    
    def _write_xml(self, df: pd.DataFrame) -> str:
        """Convert DataFrame to XML string"""
        root = ET.Element('data')
        
        for _, row in df.iterrows():
            record = ET.SubElement(root, 'record')
            for col, value in row.items():
                field = ET.SubElement(record, str(col))
                field.text = str(value)
        
        return ET.tostring(root, encoding='unicode')
    
    def _write_yaml(self, df: pd.DataFrame) -> str:
        """Convert DataFrame to YAML string"""
        data = df.to_dict(orient='records')
        return yaml.dump(data, sort_keys=False)