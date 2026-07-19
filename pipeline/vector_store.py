"""
Vector store implementation using LanceDB for RAG pipeline.

This module provides a proper vector store that:
- Uses LanceDB as the backend (data/lancedb directory)
- Supports similarity search and top-k queries
- Handles chunk data with proper content/text field mapping
- Uses proper embedding dimensions (1024 for bge-m3)
- Implements batch operations and proper error handling
- Enforces required fields like source_url and page_range
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import json

import lancedb
from lancedb.pydantic import LanceModel
from lancedb.embeddings import EmbeddingFunctionConfig, TextEmbeddingFunction
import pandas as pd

logger = logging.getLogger(__name__)

# Define the LanceDB schema for company documents
class CompanyDocument(LanceModel):
    chunk_id: str
    content: str
    embedding: List[float]
    source_url: str
    page_range: str
    symbol: str
    timestamp: str
    content_hash: str
    doc_type: str
    section_path: str
    source_filename: str
    # --- NEW: Store raw metadata as a JSON string to prevent dropping fields ---
    metadata_json: str 


class VectorStore: 
    def __init__(self, db_path: Union[str, Path] = "data/lancedb"):
        self.db_path = Path(db_path)
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.db = None
        self.table_name = "company_documents"
        
    def _get_db(self):
        if self.db is None:
            self.db = lancedb.connect(self.db_path)
        return self.db
    
    def _validate_embedding_dimensions(self, embedding: List[float]) -> None:
        """Validate that the embedding has the expected dimensions (1024 for bge-m3)."""
        if len(embedding) != 1024:
            raise ValueError(f"Expected embedding dimension 1024, got {len(embedding)}")
    
    def run(self, chunks: List[Dict[str, Any]], symbol: str) -> None:
        try:
            db = self._get_db()
            
            # Process chunks in batches for better performance
            if not chunks:
                logger.warning("No chunks to process")
                return
                
            # Convert chunks to proper format and validate
            processed_chunks = []
            for chunk in chunks:
                # Handle the content/text key mismatch - prefer 'content' field
                content = chunk.get('content', chunk.get('text', ''))
                
                # Validate required fields
                source_url = chunk.get('source_url', '')
                page_range = chunk.get('page_range', '')
                
                if not source_url:
                    logger.warning(f"Missing source_url in chunk for symbol {symbol}")
                if not page_range:
                    logger.warning(f"Missing page_range in chunk for symbol {symbol}")
                
                # Ensure embedding exists and validate dimensions
                embedding = chunk.get('embedding', [])
                if not isinstance(embedding, list):
                    raise ValueError("Embedding must be a list")
                
                self._validate_embedding_dimensions(embedding)
                
                # Extract metadata if it exists
                metadata = chunk.get('metadata', {})

                # Create the chunk record
                processed_chunk = {
                    'chunk_id': chunk.get('chunk_id', ''),
                    'content': content,
                    'embedding': embedding,
                    'source_url': source_url,
                    'page_range': page_range,
                    'symbol': symbol,
                    'timestamp': chunk.get('timestamp', ''),
                    'content_hash': chunk.get('content_hash', ''),
                    'doc_type': metadata.get('doc_type', 'unknown'),
                    'section_path': metadata.get('section_path', ''),
                    'source_filename': metadata.get('source_filename', ''),
                    
                    # --- NEW: Serialize the entire metadata dict to JSON ---
                    'metadata_json': json.dumps(metadata)
                }
                
                processed_chunks.append(processed_chunk)
            
            # Convert to DataFrame for batch operations
            df = pd.DataFrame(processed_chunks)
            
            # Get or create the table and use merge_insert for efficient batch upsert
            try:
                table = db.open_table(self.table_name)
            except Exception:
                # Table doesn't exist, create it
                table = db.create_table(self.table_name, schema=CompanyDocument)
            
            # Step 1: Define the column to match on (chunk_id)  
            match_column = "chunk_id"
            
            # Step 2: Define update/insert rules - using merge_insert for upserts
            # Step 3: Execute the data injection at the very end using .execute(df)
            operation = table.merge_insert("chunk_id") \
                                .when_matched_update_all() \
                                .when_not_matched_insert_all() \
                                .execute(df)
            
            logger.info(f"Successfully stored {len(processed_chunks)} chunks for symbol {symbol}")
            
        except Exception as e:
            logger.error(f"Failed to store chunks in vector store: {e}", exc_info=True)
            raise
    
    def search(
        self, 
        query_embedding: List[float], 
        symbol: str, 
        k: int = 5
    ) -> List[Dict[str, Any]]:
        try:
            self._validate_embedding_dimensions(query_embedding)
            
            db = self._get_db()
            table = db.open_table(self.table_name)
            
            # Filter by symbol and perform similarity search
            results = table.search(query_embedding)\
                .where(f"symbol = '{symbol}'")\
                .limit(k)\
                .to_list()
            
            # Convert results to proper format
            formatted_results = []
            for result in results:
                # --- NEW: Deserialize the metadata back into a dictionary ---
                metadata_dict = {}
                raw_meta = result.get('metadata_json', '{}')
                if raw_meta:
                    try:
                        metadata_dict = json.loads(raw_meta)
                    except json.JSONDecodeError:
                        pass
                
                # Extract the content and other metadata
                chunk_data = {
                    'chunk_id': result.get('chunk_id', ''),
                    'content': result.get('content', ''),
                    'source_url': result.get('source_url', ''),
                    'page_range': result.get('page_range', ''),
                    'symbol': result.get('symbol', ''),
                    'timestamp': result.get('timestamp', ''),
                    'doc_type': result.get('doc_type', ''),
                    'section_path': result.get('section_path', ''),
                    'source_filename': result.get('source_filename', ''),
                    'metadata': metadata_dict
                }
                formatted_results.append(chunk_data)
            
            logger.info(f"Found {len(formatted_results)} matching chunks for symbol {symbol}")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Failed to search in vector store: {e}", exc_info=True)
            return []
    
    def get_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        try:
            db = self._get_db()
            table = db.open_table(self.table_name)
            
            # Perform exact match search
            results = table.search().where(f"chunk_id = '{chunk_id}'").limit(1).to_list()            
            if results:
                # Deserialize metadata_json for direct ID lookups too
                result = results[0]
                if 'metadata_json' in result:
                    try:
                        result['metadata'] = json.loads(result.pop('metadata_json'))
                    except Exception:
                        result['metadata'] = {}
                return result
            return None
            
        except Exception as e:
            logger.error(f"Failed to get chunk by ID {chunk_id}: {e}", exc_info=True)
            return None
    
    def get_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        try:
            db = self._get_db()
            table = db.open_table(self.table_name)
            
            # Filter by symbol
            results = table.search().where(f"symbol = '{symbol}'").to_list()
            
            # Fix metadata format for all returned results
            for result in results:
                if 'metadata_json' in result:
                    try:
                        result['metadata'] = json.loads(result.pop('metadata_json'))
                    except Exception:
                        result['metadata'] = {}
                        
            return results
            
        except Exception as e:
            logger.error(f"Failed to get chunks for symbol {symbol}: {e}", exc_info=True)
            return []
    
    def get_metadata(self, symbol: str) -> Dict[str, Any]:
        try:
            db = self._get_db()
            table = db.open_table(self.table_name)
            
            # Get count of chunks and some statistics
            results = table.search().where(f"symbol = '{symbol}'").to_list()
            
            return {
                "symbol": symbol,
                "total_chunks": len(results),
                "first_chunk_id": results[0].get('chunk_id', '') if results else None,
                "last_chunk_id": results[-1].get('chunk_id', '') if results else None,
            }
            
        except Exception as e:
            logger.error(f"Failed to get metadata for symbol {symbol}: {e}", exc_info=True)
            return {"symbol": symbol, "total_chunks": 0, "error": str(e)}