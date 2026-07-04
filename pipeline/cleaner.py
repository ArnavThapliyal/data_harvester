"""
Cleaner for pipeline - cleans both numeric and document data.
"""
import os
import json
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Any
import logging
from collections import Counter

# Configure logging
logger = logging.getLogger(__name__)

class Cleaner:
    """Cleaner for pipeline that handles both numeric and document data cleaning."""
    
    def run(self, symbol: str, mode: str) -> None:
        """
        Run cleaning process for a symbol in either numeric or document mode.
        
        Args:
            symbol: Company ticker symbol
            mode: Either 'numeric' or 'document'
        """
        if mode == "numeric":
            self._clean_numeric(symbol)
        elif mode == "document":
            self._clean_document(symbol)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
        logger.info(f"[cleaner] [{symbol}] mode={mode} — done")
    
    def _clean_numeric(self, symbol: str) -> None:
        """Clean numeric data (OHLCV and fundamentals)."""
        # Input and output paths
        input_path = Path(f"data/trans/numeric/{symbol}.json")
        output_path = Path(f"data/cleaned/numeric/{symbol}.json")
        
        # Create output directory if needed
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Read input data
        if not input_path.exists():
            logger.warning(f"Numeric input file not found: {input_path}")
            return
            
        with open(input_path, 'r') as f:
            data = json.load(f)
        
        # Clean OHLCV data
        cleaned_ohlcv = []
        seen_dates = set()
        
        if "ohlcv" in data and isinstance(data["ohlcv"], list):
            for row in data["ohlcv"]:
                # Skip rows where close is null, zero, or negative
                if row.get("close") is None or row.get("close", 0) <= 0:
                    continue
                
                # Check date format validity
                date_str = row.get("date")
                if not date_str or not self._is_valid_date_format(date_str):
                    continue
                    
                # Deduplicate by date, keeping last occurrence
                if date_str in seen_dates:
                    continue
                seen_dates.add(date_str)
                
                cleaned_ohlcv.append(row)
        
        # Sort ascending by date
        cleaned_ohlcv.sort(key=lambda x: x.get("date", ""))
        
        # Clean fundamentals data - replace exactly 0 with null
        if "fundamentals" in data and isinstance(data["fundamentals"], dict):
            for key, value in data["fundamentals"].items():
                if value == 0:
                    data["fundamentals"][key] = None
        
        # Update data with cleaned OHLCV
        data["ohlcv"] = cleaned_ohlcv
        
        # Write cleaned data
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _clean_document(self, symbol: str) -> None:
        """Clean document text files."""
        # Input and output paths  
        trans_dir = Path(f"data/trans/documents/{symbol}")
        cleaned_dir = Path(f"data/cleaned/documents/{symbol}")
        
        # Create output directory if needed
        cleaned_dir.mkdir(parents=True, exist_ok=True)
        
        # Process each text file in trans directory
        for file_path in trans_dir.iterdir():
            if file_path.is_file() and file_path.suffix == ".txt":
                self._clean_text_file(file_path, cleaned_dir)
        
        # Copy index.json from trans to cleaned directory unchanged
        index_file = trans_dir / "index.json"
        if index_file.exists():
            cleaned_index = cleaned_dir / "index.json"
            with open(index_file, 'r') as f:
                index_data = json.load(f)
            with open(cleaned_index, 'w') as f:
                json.dump(index_data, f, indent=2)
    
    def _clean_text_file(self, file_path: Path, output_dir: Path) -> None:
        """Clean a single text file."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Normalize unicode
        content = unicodedata.normalize("NFKC", content)
        
        # Strip null bytes and non-printable characters while keeping \n and \t
        clean_chars = []
        for char in content:
            if char == '\x00':  # Skip null bytes
                continue
            if ord(char) < 32 and char not in ['\n', '\t']:  # Keep newlines and tabs, remove others
                continue
            clean_chars.append(char)
        content = ''.join(clean_chars)
        
        # Collapse three or more consecutive blank lines to two
        content = re.sub(r'\n\s*\n\s*\n+', '\n\n', content)
        
        # Remove lines matching Page X of Y pattern
        content = re.sub(r'^Page \d+ of \d+$', '', content, flags=re.MULTILINE)
        
        # Remove lines that are only dashes, underscores, or dots (5+ characters)
        content = re.sub(r'^[._-]{5,}$', '', content, flags=re.MULTILINE)
        
        # Write cleaned file
        output_file = output_dir / file_path.name
        with open(output_file, 'w') as f:
            f.write(content)
    
    def _is_valid_date_format(self, date_str: str) -> bool:
        """Validate that a date string parses as YYYY-MM-DD."""
        if not isinstance(date_str, str):
            return False
            
        try:
            # Check format using regex first for quick validation
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                return False
                
            # Actually parse to be sure
            from datetime import datetime
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False