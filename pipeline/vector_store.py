import os
import sqlite3
import json
import hashlib
from typing import List, Dict, Any
from datetime import datetime
from pathlib import Path

# Database configuration
DB_PATH = "data/vector_store.db"

def init_vector_store():
    """
    Initialize the vector store database with strict schema.
    
    Returns:
        sqlite3.Connection: Database connection
    """
    # Ensure directory exists
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table with strict schema - all fields must be present
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            symbol TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            source_filename TEXT NOT NULL,
            source_url TEXT,
            section_path TEXT,
            page_range TEXT,
            chunk_text TEXT NOT NULL,
            vector BLOB NOT NULL,  -- Fixed-width binary data for 1024-dimensional vectors
            downloaded_at TIMESTAMP NOT NULL,
            content_hash TEXT NOT NULL
        )
    ''')
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_symbol ON chunks(symbol)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_chunk_id ON chunks(chunk_id)')
    
    conn.commit()
    return conn

def format_chunk_data(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format chunk data to match the strict schema.
    
    Args:
        chunk (Dict): Original chunk dictionary with embedded data
        
    Returns:
        Dict: Formatted chunk matching the schema
    """
    # Extract and format required fields
    formatted_chunk = {
        'chunk_id': f"{chunk.get('metadata', {}).get('symbol', '')}_{chunk.get('content_hash', '')}",
        'symbol': chunk.get('metadata', {}).get('symbol', ''),
        'doc_type': chunk.get('metadata', {}).get('doc_type', ''),
        'source_filename': chunk.get('metadata', {}).get('source_filename', ''),
        'source_url': chunk.get('metadata', {}).get('source_url', ''),
        'section_path': chunk.get('metadata', {}).get('section_path', ''),
        'page_range': chunk.get('metadata', {}).get('page_range', ''),
        'chunk_text': chunk.get('text', ''),
        'vector': json.dumps(chunk.get('embedding', [])),  # Convert list to JSON string for storage
        'downloaded_at': chunk.get('metadata', {}).get('downloaded_at', datetime.now().isoformat()),
        'content_hash': chunk.get('content_hash', '')
    }
    
    return formatted_chunk

def upsert_chunks(chunks: List[Dict[str, Any]]) -> int:
    """
    Insert or update chunks in the vector store with idempotent behavior.
    
    Args:
        chunks (List[Dict]): List of chunk dictionaries with embeddings
        
    Returns:
        int: Number of chunks processed
    """
    conn = init_vector_store()
    cursor = conn.cursor()
    
    # Format all chunks to match schema
    formatted_chunks = [format_chunk_data(chunk) for chunk in chunks]
    
    inserted_count = 0
    
    for chunk in formatted_chunks:
        try:
            # Check if chunk already exists using chunk_id as primary key
            cursor.execute('SELECT chunk_id FROM chunks WHERE chunk_id = ?', (chunk['chunk_id'],))
            exists = cursor.fetchone()
            
            if exists:
                # Update existing record (full row update)
                cursor.execute('''
                    UPDATE chunks SET 
                        symbol = ?, doc_type = ?, source_filename = ?, source_url = ?,
                        section_path = ?, page_range = ?, chunk_text = ?, vector = ?,
                        downloaded_at = ?, content_hash = ?
                    WHERE chunk_id = ?
                ''', (
                    chunk['symbol'], chunk['doc_type'], chunk['source_filename'], 
                    chunk['source_url'], chunk['section_path'], chunk['page_range'],
                    chunk['chunk_text'], chunk['vector'], chunk['downloaded_at'], 
                    chunk['content_hash'], chunk['chunk_id']
                ))
            else:
                # Insert new record
                cursor.execute('''
                    INSERT INTO chunks (
                        chunk_id, symbol, doc_type, source_filename, source_url,
                        section_path, page_range, chunk_text, vector, downloaded_at, content_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    chunk['chunk_id'], chunk['symbol'], chunk['doc_type'], 
                    chunk['source_filename'], chunk['source_url'], chunk['section_path'],
                    chunk['page_range'], chunk['chunk_text'], chunk['vector'],
                    chunk['downloaded_at'], chunk['content_hash']
                ))
                
            inserted_count += 1
            
        except Exception as e:
            print(f"Error processing chunk {chunk.get('chunk_id', 'unknown')}: {e}")
            continue
    
    conn.commit()
    conn.close()
    
    return inserted_count

def get_chunk_by_id(chunk_id: str) -> Dict[str, Any]:
    """
    Retrieve a specific chunk by its ID.
    
    Args:
        chunk_id (str): The unique identifier for the chunk
        
    Returns:
        Dict[str, Any]: The chunk data or None if not found
    """
    conn = init_vector_store()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM chunks WHERE chunk_id = ?', (chunk_id,))
    row = cursor.fetchone()
    
    conn.close()
    
    if row:
        return {
            'chunk_id': row[0],
            'symbol': row[1],
            'doc_type': row[2],
            'source_filename': row[3],
            'source_url': row[4],
            'section_path': row[5],
            'page_range': row[6],
            'chunk_text': row[7],
            'vector': json.loads(row[8]) if row[8] else [],  # Convert back from JSON
            'downloaded_at': row[9],
            'content_hash': row[10]
        }
    
    return {}

def get_chunks_by_symbol(symbol: str) -> List[Dict[str, Any]]:
    """
    Retrieve all chunks for a specific symbol.
    
    Args:
        symbol (str): The stock symbol to query
        
    Returns:
        List[Dict[str, Any]]: List of chunk data
    """
    conn = init_vector_store()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM chunks WHERE symbol = ?', (symbol,))
    rows = cursor.fetchall()
    
    conn.close()
    
    return [
        {
            'chunk_id': row[0],
            'symbol': row[1],
            'doc_type': row[2],
            'source_filename': row[3],
            'source_url': row[4],
            'section_path': row[5],
            'page_range': row[6],
            'chunk_text': row[7],
            'vector': json.loads(row[8]) if row[8] else [],
            'downloaded_at': row[9],
            'content_hash': row[10]
        }
        for row in rows
    ]

def compact_database():
    """
    Perform database compaction to reclaim space and optimize performance.
    This should be run periodically as part of maintenance routine.
    """
    conn = init_vector_store()
    
    try:
        # Perform VACUUM to reclaim space and optimize
        cursor = conn.cursor()
        cursor.execute('VACUUM')
        conn.commit()
        print("Database compaction completed successfully.")
    except Exception as e:
        print(f"Database compaction failed: {e}")
    finally:
        conn.close()

def main():
    """
    Sample usage example. This would typically be called by the main pipeline after embedding.
    """
    # Test with sample data
    test_chunks = [
        {
            "text": "This is the first test document.",
            "metadata": {
                "symbol": "TEST1", 
                "source_filename": "test.md", 
                "doc_type": "annual_report",
                "downloaded_at": datetime.now().isoformat()
            },
            "content_hash": hashlib.sha256("This is the first test document.".encode()).hexdigest(),
            "embedding": [0.1] * 1024  # Mock embedding vector
        }
    ]
    
    print("Uploading test data to vector store...")
    count = upsert_chunks(test_chunks)
    print(f"Uploaded {count} chunks")

if __name__ == "__main__":
    main()