"""
DataForge data models and schemas
"""
from pydantic import BaseModel
from typing import List, Optional, Dict

class ConversionRequest(BaseModel):
    content: str
    from_format: str
    to_format: str
    transformations: Optional[List[str]] = []

class FormatResponse(BaseModel):
    formats: List[str]