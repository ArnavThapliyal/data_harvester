"""
Embedder for pipeline - generates embeddings for text chunks using BAAI/bge-m3.

This implementation follows the requirements:
1. Initialization and hardware binding (MPS, CUDA, or CPU)
2. Idempotency layer (deduplication with SQLite database)  
3. Batching strategy
4. Embedding execution with BAAI/bge-m3 model
5. Assembly and handoff to vector store

"""
import os
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any
import logging
import sqlite3
import torch
from sentence_transformers import SentenceTransformer
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)

# Global embedding model and device
_model = None
_device = None


def get_device():
    """Select appropriate computing device."""
    global _device
    if _device is None:
        # Try to use MPS (Apple Silicon) first for macOS
        if torch.backends.mps.is_available():
            _device = "mps"
        elif torch.cuda.is_available():
            _device = "cuda"
        else:
            _device = "cpu"
    return _device


def load_embedding_model():
    """Load the embedding model and bind to appropriate device."""
    global _model
    if _model is None:
        print(f"Loading BAAI/bge-m3 model...")
        device = get_device()
        _model = SentenceTransformer("BAAI/bge-m3", device=device)
        print(f"Model loaded successfully on {device}")
        
        # Verify output dimensions for consistency
        sample_embedding = _model.encode("test")
        expected_dims = 1024  # BAAI/bge-m3 produces 1024-dimensional vectors
        actual_dims = len(sample_embedding)
        
        if actual_dims != expected_dims:
            raise ValueError(
                f"Model output dimension mismatch: expected {expected_dims}, got {actual_dims}. "
                "Please verify your embedding model and vector database schema match."
            )
            
    return _model


def initialize_vector_db():
    """
    Initialize the SQLite-based deduplication index.
    
    Returns:
        sqlite3.Connection: Database connection
    """
    # Ensure directory exists
    Path("data").mkdir(parents=True, exist_ok=True)
    
    db_path = "data/embedding_index.db"
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create embedding_index table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS embedding_index (
            content_hash TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    return conn


def check_deduplication(chunk: Dict[str, Any], db_conn) -> bool:
    """
    Check if chunk has already been embedded.
    
    Args:
        chunk (Dict): Dictionary containing chunk data and metadata
        db_conn: SQLite database connection
        
    Returns:
        bool: True if chunk is new, False if already exists
    """
    cursor = db_conn.cursor()
    
    # Get content hash from chunk
    content_hash = chunk.get('content_hash', '')
    
    if not content_hash:
        return True  # If no hash, assume new
    
    # Check if hash exists in database
    cursor.execute('SELECT 1 FROM embedding_index WHERE content_hash = ?', (content_hash,))
    result = cursor.fetchone()
    
    return result is None  # Return True if not found (i.e., new)


def add_to_deduplication_index(chunk: Dict[str, Any], db_conn) -> None:
    """
    Add chunk's content hash to deduplication index.
    
    Args:
        chunk (Dict): Dictionary containing chunk data and metadata
        db_conn: SQLite database connection
    """
    cursor = db_conn.cursor()
    
    # Get content hash from chunk
    content_hash = chunk.get('content_hash', '')
    
    if not content_hash:
        return  # Skip if no hash
        
    # Insert or ignore (in case of duplicate)
    cursor.execute(
        'INSERT OR IGNORE INTO embedding_index (content_hash) VALUES (?)',
        (content_hash,)
    )
    
    db_conn.commit()


def batch_chunks(chunks: List[Dict[str, Any]], batch_size: int = 32) -> List[List[Dict[str, Any]]]:
    """
    Split chunks into batches for processing.
    
    Args:
        chunks (List[Dict]): List of chunk dictionaries
        batch_size (int): Size of each batch
        
    Returns:
        List[List[Dict]]: List of batched chunk lists
    """
    batches = []
    for i in range(0, len(chunks), batch_size):
        batches.append(chunks[i:i + batch_size])
        
    return batches


def extract_texts_from_chunks(chunks: List[Dict[str, Any]]) -> List[str]:
    """
    Extract text content from chunk dictionaries.
    
    Args:
        chunks (List[Dict]): List of chunk dictionaries
        
    Returns:
        List[str]: List of plain text strings
    """
    return [chunk['text'] for chunk in chunks]


def embed_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Main function to embed chunks with deduplication.
    
    Args:
        chunks (List[Dict]): List of chunk dictionaries
        
    Returns:
        List[Dict]: List of dictionaries with added embeddings
    """
    # Load model
    model = load_embedding_model()
    
    # Initialize database connection
    db_conn = initialize_vector_db()
    
    # Filter out already embedded chunks
    new_chunks = []
    skipped_count = 0
    
    print(f"Processing {len(chunks)} chunks...")
    
    for chunk in chunks:
        if check_deduplication(chunk, db_conn):
            new_chunks.append(chunk)
        else:
            skipped_count += 1
    
    print(f"Skipped {skipped_count} already-embedded chunks.")
    
    # If no new chunks, return empty list
    if not new_chunks:
        print("All chunks were already embedded.")
        return []
        
    # Batch the new chunks for processing
    batches = batch_chunks(new_chunks)
    
    # Process each batch
    embedded_chunks = []
    processed_in_current_batch = 0
    
    for i, batch in enumerate(batches):
        print(f"Processing batch {i+1}/{len(batches)}...")
        
        # Extract texts and corresponding indices for mapping back
        batch_texts = extract_texts_from_chunks(batch)
        
        # Generate embeddings
        embeddings = model.encode(batch_texts)
        
        # Zip embeddings back to chunks
        for j, (chunk, embedding) in enumerate(zip(batch, embeddings)):
            chunk['embedding'] = embedding.tolist()  # Convert numpy array to list
            embedded_chunks.append(chunk)
            processed_in_current_batch += 1
            
            # Add to deduplication index
            add_to_deduplication_index(chunk, db_conn)
    
    print(f"Completed processing. Embedded {processed_in_current_batch} chunks.")
    print(f"Total skipped: {skipped_count}")
    
    # Close database connection
    db_conn.close()
    
    return embedded_chunks


class Embedder:
    """Embedder that processes text chunks and generates vector embeddings."""
    
    def __init__(self):
        # Embedding model already loaded globally, but we keep this for compatibility
        self.embedding_dim = 1024  # produces 1024-dimensional vectors
        
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
        
        # Collect chunks and add them to embedder list
        all_chunks = []
        for chunk in chunk_data.get("chunks", []):
            # Make sure content_hash exists
            if "content_hash" not in chunk:
                chunk["content_hash"] = hashlib.sha256(chunk["content"].encode()).hexdigest()
                
            all_chunks.append(chunk)
        
        # Embed all chunks
        embedded_chunks = embed_chunks(all_chunks)
        
        # Update the chunk data with embeddings  
        chunk_data["chunks"] = embedded_chunks
        
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


# For testing purposes
if __name__ == "__main__":
    # Create some test data
    chunks = [
        {
            "text": "This is the first test document.",
            "metadata": {
                "symbol": "TEST1", 
                "source_filename": "test.md", 
                "doc_type": "annual_report",
                "downloaded_at": "2023-01-01T00:00:00Z"
            },
            "content_hash": hashlib.sha256("This is the first test document.".encode()).hexdigest()
        },
        {
            "text": "This is the second test document.",
            "metadata": {
                "symbol": "TEST2", 
                "source_filename": "test.md", 
                "doc_type": "annual_report",
                "downloaded_at": "2023-01-01T00:00:00Z"
            },
            "content_hash": hashlib.sha256("This is the second test document.".encode()).hexdigest()
        }
    ]
    
    print("Starting embedding process...")
    result = embed_chunks(chunks)
    print(f"Result contains {len(result)} embedded chunks")