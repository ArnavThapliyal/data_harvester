"""Abstract base classes and interfaces for collectors."""

from abc import ABC, abstractmethod
from typing import List, Any, Dict
from pathlib import Path


class BaseCollector(ABC):
    """Base interface for all data collectors."""
    
    @abstractmethod
    def collect(self) -> List[Dict[str, Any]]:
        """Collect data from source and return list of records."""
        pass
    
    @abstractmethod
    def validate(self, data: List[Dict[str, Any]]) -> bool:
        """Validate collected data."""
        pass


class NumericCollector(BaseCollector):
    """Base interface for numeric data collectors."""
    
    @abstractmethod
    def normalize(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize and standardize numeric data."""
        pass


class DocumentCollector(BaseCollector):
    """Base interface for document collectors."""
    
    @abstractmethod
    def process_document(self, raw_content: str) -> Dict[str, Any]:
        """Process raw document content into structured format."""
        pass
