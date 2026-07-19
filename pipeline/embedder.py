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
from typing import List, Dict, Any, Set
import logging
import torch
import lancedb
from sentence_transformers import SentenceTransformer
import numpy as np

# Must match VectorStore's db_path/table_name in vector_store.py — dedup
# and storage now read/write the same table, so these can't drift apart.
# [CONFIRM] move both to config.settings once that's the shared source of truth.
LANCEDB_PATH = "data/lancedb"
LANCEDB_TABLE = "company_documents"

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

def get_existing_hashes(content_hashes: List[str]) -> Set[str]:
    """
    Which of these content_hashes are already sitting in LanceDB.

    Replaces the old standalone data/embedding_index.db SQLite tracker —
    that was a second source of truth for a fact vector_store.py's schema
    already stores per row (content_hash). One bulk IN-filter query here
    instead of a per-chunk SQLite round trip.
    """
    if not content_hashes:
        return set()

    try:
        db = lancedb.connect(LANCEDB_PATH)
        table = db.open_table(LANCEDB_TABLE)
    except Exception:
        # Table doesn't exist yet — first run, nothing is indexed.
        return set()

    quoted = ",".join(f"'{h}'" for h in content_hashes)
    rows = (
        table.search()
        .where(f"content_hash IN ({quoted})")
        .select(["content_hash"])
        .to_list()
    )
    return {row["content_hash"] for row in rows}


def batch_chunks(chunks: List[Dict[str, Any]], batch_size: int = 32) -> List[List[Dict[str, Any]]]:
    batches = []
    for i in range(0, len(chunks), batch_size):
        batches.append(chunks[i:i + batch_size])
        
    return batches


def extract_texts_from_chunks(chunks: List[Dict[str, Any]]) -> List[str]:
    return [chunk['content'] for chunk in chunks]


def embed_chunks(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Load model
    model = load_embedding_model()

    # Bulk-check LanceDB for hashes already indexed from a prior run.
    incoming_hashes = [c.get('content_hash', '') for c in chunks if c.get('content_hash')]
    existing_hashes = get_existing_hashes(incoming_hashes)

    # Filter out already-indexed chunks, and dedup *within this call* too —
    # the old sqlite version caught intra-batch duplicates by writing to
    # its index as it went; a single bulk query up front doesn't, so track
    # hashes seen in this batch explicitly.
    new_chunks = []
    seen_this_call: Set[str] = set()
    skipped_count = 0

    print(f"Processing {len(chunks)} chunks...")

    for chunk in chunks:
        content_hash = chunk.get('content_hash', '')
        if not content_hash:
            new_chunks.append(chunk)  # no hash -> treat as new, same as before
            continue
        if content_hash in existing_hashes or content_hash in seen_this_call:
            skipped_count += 1
            continue
        seen_this_call.add(content_hash)
        new_chunks.append(chunk)

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
            # No separate index write — VectorStore().run() downstream is
            # the single write path that makes this hash "known" next time.

    print(f"Completed processing. Embedded {processed_in_current_batch} chunks.")
    print(f"Total skipped: {skipped_count}")

    return embedded_chunks


class Embedder:    
    def __init__(self):
        # Embedding model already loaded globally, but we keep this for compatibility
        self.embedding_dim = 1024  # produces 1024-dimensional vectors
        
    def run(self, symbol: str) -> None:
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