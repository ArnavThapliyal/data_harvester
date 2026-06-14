"""
Embedder for pipeline - generates embeddings for text chunks.
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Any
import logging
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)

class Embedder:
    """Embedder that processes text chunks and generates vector embeddings."""
    
    def __init__(self):
        # For demonstration purposes - would normally use actual embedding model
        self.embedding_dim = 384  # Common dimension for sentence transformers
        
    def run(self, symbol: str) -> None:
        """
        Run embedding process for a symbol.
        
        Args:
            symbol: Company ticker symbol
        """
        # Input and output paths
        input_dir = Path(f"data/chunked/{symbol}")
        output_dir = Path(f"data/embedded/{symbol}")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"[embedder] [{symbol}] starting embedding")
        
        # Process each chunk file in the chunked directory
        for file_path in input_dir.iterdir():
            if file_path.is_file() and file_path.suffix == ".json":
                self._embed_file(file_path, output_dir)
        
        logger.info(f"[embedder] [{symbol}] completed embedding")
    
    def _embed_file(self, file_path: Path, output_dir: Path) -> None:
        """Generate embeddings for a single chunked file."""
        with open(file_path, 'r') as f:
            chunk_data = json.load(f)
        
        # For each chunk, generate a dummy embedding (in real implementation, 
        # this would use something like sentence-transformers or similar library)
        processed_chunks = []
        
        for chunk in chunk_data.get("chunks", []):
            # Create a simple dummy embedding - in practice this would be 
            # generated from the actual text content
            dummy_embedding = self._generate_dummy_embedding(chunk["content"])
            
            chunk_with_embedding = {
                **chunk,
                "embedding": dummy_embedding,
                "embedding_dim": len(dummy_embedding)
            }
            
            processed_chunks.append(chunk_with_embedding)
        
        # Update the chunk data with embeddings
        chunk_data["chunks"] = processed_chunks
        
        # Write the embedding data to output directory
        output_file = output_dir / file_path.name
        with open(output_file, 'w') as f:
            json.dump(chunk_data, f, indent=2)
    
    def _generate_dummy_embedding(self, text: str) -> List[float]:
        """
        Generate a dummy embedding for demonstration purposes.
        
        In a real implementation, this would use an actual embedding model
        like sentence-transformers or OpenAI embeddings.
        """
        # Simple hash-based approach for demonstration
        # In practice, replace with actual model inference
        
        # Normalize the text and create a simple numeric representation
        normalized_text = text.lower().strip()
        hash_sum = sum(ord(c) * (i + 1) for i, c in enumerate(normalized_text))
        
        # Create dummy vector of fixed dimension
        embedding = []
        for i in range(self.embedding_dim):
            # Simple pseudo-random generation based on hash
            seed = hash_sum + i * 7
            val = (seed * 234561 + 12345) % 1000000
            normalized_val = (val / 1000000.0) - 0.5  # Normalize to ~[-0.5, 0.5]
            embedding.append(normalized_val)
            
        return embedding