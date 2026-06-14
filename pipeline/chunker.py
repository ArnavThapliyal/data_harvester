"""
Chunker for pipeline - splits cleaned text into manageable chunks.
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Any
import logging

# Configure logging
logger = logging.getLogger(__name__)

class Chunker:
    """Chunker that processes cleaned document text and splits into manageable pieces."""
    
    def __init__(self):
        self.chunk_size = 1000  # characters per chunk
        self.overlap_size = 100  # overlapping characters between chunks
        
    def run(self, symbol: str) -> None:
        """
        Run chunking process for a symbol.
        
        Args:
            symbol: Company ticker symbol
        """
        # Input and output paths
        input_dir = Path(f"data/cleaned/documents/{symbol}")
        output_dir = Path(f"data/chunked/{symbol}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[chunker] [{symbol}] starting chunking")
        
        # Process each text file in the cleaned directory
        for file_path in input_dir.iterdir():
            if file_path.is_file() and file_path.suffix == ".txt":
                self._chunk_file(file_path, output_dir)
        
        logger.info(f"[chunker] [{symbol}] completed chunking")
    
    def _chunk_file(self, file_path: Path, output_dir: Path) -> None:
        """Chunk a single text file into overlapping segments."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        # If content is too short, write as single chunk
        if len(content) <= self.chunk_size:
            chunk_data = {
                "original_file": file_path.name,
                "chunks": [{
                    "chunk_id": 0,
                    "content": content,
                    "start_pos": 0,
                    "end_pos": len(content)
                }]
            }
        else:
            # Create overlapping chunks
            chunks = []
            start = 0
            chunk_id = 0
            
            while start < len(content):
                end = min(start + self.chunk_size, len(content))
                
                # Adjust to word boundary if not at beginning
                if start > 0:
                    # Find the last space before the chunk end to avoid cutting words
                    word_end = content.rfind(' ', start, end)
                    if word_end != -1 and word_end > start + 20:  # Only adjust if we're not near the start
                        end = word_end + 1  # Include the space
                elif end < len(content) and content[end] != ' ':  
                    # If at beginning, find next word boundary
                    word_start = content.find(' ', end)
                    if word_start != -1:
                        end = word_start
                
                chunk_text = content[start:end]
                
                chunks.append({
                    "chunk_id": chunk_id,
                    "content": chunk_text,
                    "start_pos": start,
                    "end_pos": end
                })
                
                # Move start position forward with overlap
                start = max(0, end - self.overlap_size)
                chunk_id += 1
                
                if start >= len(content):
                    break
            
            chunk_data = {
                "original_file": file_path.name,
                "chunks": chunks
            }
        
        # Write chunked data to output directory
        output_file = output_dir / f"{file_path.stem}_chunks.json"
        with open(output_file, 'w') as f:
            json.dump(chunk_data, f, indent=2)