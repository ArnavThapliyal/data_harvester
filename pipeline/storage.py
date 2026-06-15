"""Storage interface and implementations for the data harvester pipeline."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List
import json
import os

from config.settings import (
    RAW_NUMERIC, 
    RAW_DOCUMENTS, 
    TRANS_NUMERIC, 
    TRANS_DOCUMENTS,
    CLEANED_NUMERIC,
    CLEANED_DOCUMENTS,
    CHUNKED,
    DONE
)


def save_raw(doc: dict, base_dir: Path) -> Path:
    """Save raw document and its metadata sidecar."""
    dest = base_dir / doc.source / doc.company_id / doc.doc_type
    dest.mkdir(parents=True, exist_ok=True)
    
    # Save content
    file_path = dest / f"{doc.metadata['date']}_{doc.metadata['accession']}.html"
    file_path.write_bytes(doc.raw_content)
    
    # Save metadata sidecar — same name, .meta.json extension
    meta_path = file_path.with_suffix('.meta.json')
    meta_path.write_text(json.dumps(doc.metadata, indent=2))
    
    return file_path


class StorageProvider:
    """Interface for storing collected data."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        # All paths are already created in settings.py
        
    def store_collected_data(self, collector, records: List[Dict[str, Any]]):
        """Store collected records in appropriate location based on collector type."""
        if hasattr(collector, '__class__'):
            collector_name = collector.__class__.__name__.lower()
            
            # Determine where to store based on collector name
            if 'numeric' in collector_name:
                output_dir = RAW_NUMERIC
            elif 'document' in collector_name:
                output_dir = RAW_DOCUMENTS
            else:
                output_dir = TRANS_NUMERIC
            
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Store each record with a unique identifier
            for i, record in enumerate(records):
                filename = f"{collector_name}_{i}.json"
                file_path = output_dir / filename
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(record, f, indent=2, ensure_ascii=False)
                    
    def store_document(self, document, path: Path):
        """Store a single document."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(document, f, indent=2, ensure_ascii=False) 
            
    def load_document(self, path: Path) -> Dict[str, Any]:
        """Load a single document."""
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}