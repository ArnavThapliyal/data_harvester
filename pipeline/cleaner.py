"""
Cleaner for pipeline - cleans both numeric and document data.
"""
import os
import json
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Set
import logging
from collections import Counter

# Configure logging
logger = logging.getLogger(__name__)

class Cleaner:
    """Cleaner for pipeline that handles both numeric and document data cleaning."""
    
    # Static denylist for boilerplate text
    DENYLIST_PATTERNS = [
        "Scanned with CamScanner",
        "Powered by",
        "Confidential",
        "Copyright",
        "All rights reserved",
        "Page \\d+ of \\d+",  # Page X of Y pattern
        "^[._-]{5,}$",       # Lines with 5+ dashes/underscores/dots
    ]
    
    def __init__(self):
        """Initialize the cleaner with configuration."""
        pass
    
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
        
        # Process each file in trans directory
        for file_path in trans_dir.iterdir():
            if file_path.is_file() and file_path.suffix == ".json":
                self._clean_json_file(file_path, cleaned_dir)
    
    def _clean_json_file(self, file_path: Path, output_dir: Path) -> None:
        """Clean a single JSON file containing IR blocks."""
        with open(file_path, 'r') as f:
            ir_blocks = json.load(f)
        
        # Apply cleaning to the IR blocks
        cleaned_blocks = self._clean_ir_blocks(ir_blocks)
        
        # Write cleaned file
        output_file = output_dir / file_path.name
        with open(output_file, 'w') as f:
            json.dump(cleaned_blocks, f, indent=2)
    
    def _clean_ir_blocks(self, ir_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply the complete cleaning workflow to IR blocks:
        1. Page-aware grouping
        2. Dynamic frequency analysis for headers/footers
        3. Static denylist filtering 
        4. Execution with stripping and normalization
        
        Args:
            ir_blocks: List of IR blocks from parser
            
        Returns:
            Cleaned list of IR blocks
        """
        # Step 1: Page-aware grouping
        page_groups = self._group_by_page(ir_blocks)
        
        # Step 2: Dynamic filter - frequency analysis for headers/footers
        dynamic_deletion_set = self._detect_dynamic_deletion_candidates(page_groups)
        
        # Step 3: Static filter - denylist patterns
        static_deletion_set = self._build_static_deletion_set()
        
        # Combine both deletion sets
        combined_deletion_set = dynamic_deletion_set.union(static_deletion_set)
        
        # Step 4: Execution - stripping and normalizing
        cleaned_blocks = []
        for block in ir_blocks:
            # Check if this block should be deleted based on its exact text match
            if block.get('content') and block['content'] in combined_deletion_set:
                # Skip this block entirely
                continue
            
            # Normalize surviving blocks
            cleaned_block = self._normalize_block(block)
            cleaned_blocks.append(cleaned_block)
        
        return cleaned_blocks
    
    def _group_by_page(self, ir_blocks: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
        """
        Group all text blocks by their page_number attribute.
        
        Args:
            ir_blocks: Flat list of IR blocks
            
        Returns:
            Dictionary mapping page numbers to lists of blocks on that page
        """
        page_groups = {}
        
        for block in ir_blocks:
            page_num = block.get('page_number', 1)
            if page_num not in page_groups:
                page_groups[page_num] = []
            page_groups[page_num].append(block)
            
        return page_groups
    
    def _detect_dynamic_deletion_candidates(self, page_groups: Dict[int, List[Dict[str, Any]]]) -> Set[str]:
        """
        Detect and tag headers, footers, and page-numbered text using frequency analysis.
        
        Args:
            page_groups: Dictionary mapping page numbers to lists of blocks
            
        Returns:
            Set of text strings that should be deleted
        """
        # Collect short paragraph/heading blocks (length < 80)
        short_blocks = []
        for page_num, blocks in page_groups.items():
            for block in blocks:
                if (block.get('type') in ['paragraph', 'header'] and 
                    isinstance(block.get('content'), str) and
                    len(block['content']) < 80):
                    short_blocks.append(block)
        
        # Count unique pages per string across the entire document
        string_page_count = Counter()
        string_to_pages = {}  # To track which pages each string appears on
        
        for block in short_blocks:
            content = block.get('content', '').strip()
            if content and len(content) > 0:  # Skip empty strings 
                string_page_count[content] += 1
                if content not in string_to_pages:
                    string_to_pages[content] = set()
                string_to_pages[content].add(block.get('page_number', 1))
        
        # Determine deletion candidates: strings that appear on multiple different pages
        deletion_set = set()
        threshold = 3  # Minimum number of distinct pages for being flagged
        
        for text, page_set in string_to_pages.items():
            if len(page_set) >= threshold:
                deletion_set.add(text)
                
        logger.info(f"Detected {len(deletion_set)} dynamic deletion candidates")
        return deletion_set
    
    def _build_static_deletion_set(self) -> Set[str]:
        """
        Build the static denylist set combining patterns and text strings.
        
        Returns:
            Set of text strings that should be deleted
        """
        # Start with exact text matches from denylist
        static_set = set()
        
        for pattern in self.DENYLIST_PATTERNS:
            # If it's a simple string (not regex), add it directly
            if not re.search(r'[.*+?^${}()|[\]\\]', pattern):  # Check if it contains regex chars
                static_set.add(pattern)
        
        return static_set
    
    def _normalize_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize text content in a block, preserving table structures.
        
        Args:
            block: IR block to normalize
            
        Returns:
            Normalized IR block 
        """
        # Create a copy of the block
        normalized_block = block.copy()
        
        # Only normalize if content exists and block is not a table
        if (isinstance(normalized_block.get('content'), str) and 
            normalized_block.get('type') != 'table'):
            
            content = normalized_block['content']
            
            # Collapse excessive whitespace to single space
            normalized_content = re.sub(r'\s+', ' ', content)
            
            # Strip leading/trailing whitespace  
            normalized_content = normalized_content.strip()
            
            # Update the block with normalized content
            normalized_block['content'] = normalized_content
            
        return normalized_block
    
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