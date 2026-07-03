"""
Normalizer for pipeline - standardizes and unifies data from all sources.
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Any
import logging
import hashlib
import yaml # pyyaml for YAML parsing
import datetime
import re # doc type matching 

# Configure logging
logger = logging.getLogger(__name__)

class Normalizer:
    """Normalizer that standardizes and unifies data from all stages."""
    
    def __init__(self):
        self.schema_version = "1.0"
        
    def run(self, symbol: str) -> None:
        """
        Run normalization process for a symbol.
        
        Args:
            symbol: Company ticker symbol
        """
        logger.info(f"[normalizer] [{symbol}] starting normalization")
        
        # Load cleaned numeric data
        numeric_input = Path(f"data/cleaned/numeric/{symbol}.json")
        numeric_data = None
        if numeric_input.exists():
            with open(numeric_input, 'r') as f:
                numeric_data = json.load(f)
        
        # Load cleaned document data and chunked data
        document_input = Path(f"data/cleaned/documents/{symbol}")
        chunked_input = Path(f"data/chunked/{symbol}")
        
        combined_data = {
            "symbol": symbol,
            "schema_version": self.schema_version,
            "metadata": {
                "created_at": None,  # Would be set by pipeline
                "source": "data_harvester",
                "processed_files": []
            },
            "numeric_data": numeric_data,
            "document_chunks": [],
            "fundamentals": {}
        }
        
        # Process document chunks if they exist
        if chunked_input.exists():
            for chunk_file in chunked_input.iterdir():
                if chunk_file.is_file() and chunk_file.suffix == ".json":
                    with open(chunk_file, 'r') as f:
                        chunk_data = json.load(f)
                    
                    # Extract chunk information and add to combined data
                    file_name = chunk_file.name.replace("_chunks.json", "")
                    for chunk in chunk_data.get("chunks", []):
                        normalized_chunk = {
                            "chunk_id": chunk["chunk_id"],
                            "content": chunk["content"],
                            "start_pos": chunk["start_pos"],
                            "end_pos": chunk["end_pos"],
                            "original_file": file_name,
                            "embedding": chunk.get("embedding") if "embedding" in chunk else None
                        }
                        combined_data["document_chunks"].append(normalized_chunk)
        
        # Create or update the normalized output file
        output_dir = Path(f"data/normalized/{symbol}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f"{symbol}.json"
        
        # Add a metadata field with creation timestamp (would be populated by orchestrator)
        combined_data["metadata"]["created_at"] = self._get_timestamp()
        
        # Write final normalized data
        with open(output_file, 'w') as f:
            json.dump(combined_data, f, indent=2)
        
        logger.info(f"[normalizer] [{symbol}] completed normalization")
    
    def _get_timestamp(self) -> str:
        """Generate a timestamp for the normalized data."""
        from datetime import datetime
        return datetime.utcnow().isoformat() + "+00:00"
    
    def merge_symbol_data(self, symbol: str, data: Dict[str, Any]) -> None:
        """
        Merge additional data for a symbol (used by orchestrator).
        
        Args:
            symbol: Company ticker symbol
            data: Additional data to merge in
        """
        output_dir = Path(f"data/normalized/{symbol}")
        output_file = output_dir / f"{symbol}.json"
        
        if output_file.exists():
            with open(output_file, 'r') as f:
                existing_data = json.load(f)
            
            # Merge the new data into existing
            for key, value in data.items():
                if key in existing_data and isinstance(existing_data[key], dict) and isinstance(value, dict):
                    # Deep merge dictionaries
                    existing_data[key].update(value)
                else:
                    existing_data[key] = value
            
            # Write updated file
            with open(output_file, 'w') as f:
                json.dump(existing_data, f, indent=2)