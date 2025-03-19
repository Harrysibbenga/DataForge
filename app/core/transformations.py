"""
core/transformations.py - Data transformation functions
"""
import pandas as pd
import re
from typing import List, Dict, Any, Callable, Union
import numpy as np

def remove_empty_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Remove rows where all values are NaN or empty strings"""
    # Make a copy to avoid modifying the original
    df = df.copy()
    
    # Convert empty strings to NaN for all object/string columns
    for col in df.select_dtypes(include=['object']):
        df.loc[df[col].astype(str).str.strip() == '', col] = np.nan
    
    # Drop rows where all values are NaN
    result = df.dropna(how='all').reset_index(drop=True)
    
    return result

def remove_empty_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Remove columns where all values are NaN or empty strings"""
    return df.dropna(axis=1, how='all')

def rename_columns(df: pd.DataFrame, mapping: Dict[str, str]) -> pd.DataFrame:
    """Rename columns according to the provided mapping"""
    return df.rename(columns=mapping)

def convert_column_types(df: pd.DataFrame, type_mapping: Dict[str, str]) -> pd.DataFrame:
    """
    Convert column types according to the provided mapping
    
    Args:
        df: Input DataFrame
        type_mapping: Dict mapping column names to types ('int', 'float', 'str', 'date', 'bool')
    
    Returns:
        DataFrame with converted column types
    """
    df = df.copy()
    
    for col, col_type in type_mapping.items():
        if col not in df.columns:
            continue
            
        if col_type == 'int':
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(int)
        elif col_type == 'float':
            df[col] = pd.to_numeric(df[col], errors='coerce')
        elif col_type == 'str':
            df[col] = df[col].astype(str)
        elif col_type == 'date':
            df[col] = pd.to_datetime(df[col], errors='coerce')
        elif col_type == 'bool':
            df[col] = df[col].astype(bool)
    
    return df

def trim_whitespace(df: pd.DataFrame, columns: List[str] = None) -> pd.DataFrame:
    """
    Trim whitespace from string columns
    
    Args:
        df: Input DataFrame
        columns: List of column names to process. If None, process all string columns.
    
    Returns:
        DataFrame with trimmed string values
    """
    df = df.copy()
    
    # If no columns specified, process all string columns
    if columns is None:
        columns = df.select_dtypes(include=['object']).columns
    
    for col in columns:
        if col in df.columns and df[col].dtype == 'object':
            df[col] = df[col].str.strip()
    
    return df

def filter_rows(df: pd.DataFrame, condition_func: Callable[[pd.Series], bool]) -> pd.DataFrame:
    """
    Filter rows based on a condition function
    
    Args:
        df: Input DataFrame
        condition_func: Function that takes a row (as Series) and returns True/False
    
    Returns:
        Filtered DataFrame
    """
    return df[df.apply(condition_func, axis=1)].reset_index(drop=True)

def standardize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize column names:
    - Convert to lowercase
    - Replace spaces and hyphens with underscores
    - Remove special characters
    
    Returns:
        DataFrame with standardized column names
    """
    df = df.copy()
    
    # Function to standardize a single column name
    def standardize_name(name):
        # Convert to lowercase
        name = name.lower()
        # Replace spaces and hyphens with underscores
        name = name.replace(' ', '_').replace('-', '_')
        # Remove special characters except underscores
        name = re.sub(r'[^a-z0-9_]', '', name)
        # Ensure the name doesn't start with a number
        if name and name[0].isdigit():
            name = 'col_' + name
        return name
    
    # Create a mapping of old names to new names
    name_mapping = {col: standardize_name(col) for col in df.columns}
    
    # Apply the mapping
    df = df.rename(columns=name_mapping)
    
    return df

def deduplicate_rows(df: pd.DataFrame, subset: List[str] = None) -> pd.DataFrame:
    """
    Remove duplicate rows
    
    Args:
        df: Input DataFrame
        subset: List of column names to consider for identifying duplicates.
               If None, use all columns.
    
    Returns:
        DataFrame with duplicates removed
    """
    return df.drop_duplicates(subset=subset).reset_index(drop=True)

def impute_missing_values(df: pd.DataFrame, strategy: Dict[str, str]) -> pd.DataFrame:
    """
    Impute missing values according to the provided strategy
    
    Args:
        df: Input DataFrame
        strategy: Dict mapping column names to imputation strategies
                 ('mean', 'median', 'mode', 'zero', 'value:X')
    
    Returns:
        DataFrame with imputed values
    """
    df = df.copy()
    
    for col, method in strategy.items():
        if col not in df.columns:
            continue
            
        if method == 'mean':
            df[col] = df[col].fillna(df[col].mean())
        elif method == 'median':
            df[col] = df[col].fillna(df[col].median())
        elif method == 'mode':
            df[col] = df[col].fillna(df[col].mode()[0])
        elif method == 'zero':
            df[col] = df[col].fillna(0)
        elif method.startswith('value:'):
            value = method.split(':', 1)[1]
            # Try to convert to numeric if possible
            try:
                value = float(value)
            except ValueError:
                pass
            df[col] = df[col].fillna(value)
    
    return df

def create_transformation_pipeline(transformations: List[Callable]) -> Callable:
    """
    Create a pipeline of transformation functions
    
    Args:
        transformations: List of transformation functions
    
    Returns:
        Function that applies all transformations in sequence
    """
    def pipeline(df: pd.DataFrame) -> pd.DataFrame:
        result = df.copy()
        for transform_func in transformations:
            result = transform_func(result)
        return result
    
    return pipeline