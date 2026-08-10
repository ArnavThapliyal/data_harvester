# Data Processing and Transformation

## Overview
The data processing pipeline transforms raw collected data into structured, searchable knowledge. It consists of several stages that work together to clean, chunk, embed, and normalize data.

## Pipeline Stages

### 1. Cleaner (pipeline/cleaner.py)
- Removes noise from parsed document content
- Normalizes text formatting and structure
- Maintains document structure while cleaning up extraneous elements
- Converts content into a standardized format for subsequent processing

### 2. Chunker (pipeline/chunker.py)
- Breaks cleaned text into manageable chunks
- Uses appropriate chunking strategies for different document types
- Maintains semantic coherence within chunks
- Handles overlapping content when appropriate

### 3. Embedder (pipeline/embedder.py)
- Converts text chunks into vector embeddings
- Uses sentence transformers for semantic understanding
- Caches embeddings to avoid recomputation
- Handles deduplication of similar chunks

### 4. Normalizer (pipeline/normalizer.py)
- Unifies data from different sources into a common schema
- Ensures consistent metadata structure across all documents
- Applies final formatting and validation
- Prepares data for export

### 5. Indexer (pipeline/indexer.py)
- Main integration point that orchestrates the conversion pipeline
- Handles the complete flow: parse → clean → chunk → embed → upsert
- Manages temporary directories for intermediate processing
- Integrates with LanceDB vector store for storage

## Processing Flow

### Document Processing Pipeline (Indexer)
1. **Parse**: Extract content from raw documents using appropriate parsers
2. **Clean**: Remove noise and normalize text structure 
3. **Chunk**: Break content into semantic chunks
4. **Embed**: Convert chunks to vector embeddings
5. **Upsert**: Store embeddings in LanceDB with metadata

### Key Features of the Processing Pipeline
- **In-memory processing**: All stages work in memory between steps
- **Atomic file processing**: Each document is processed as a unit
- **Error isolation**: Failed files don't affect other documents in the same symbol
- **Metadata preservation**: All source information is maintained throughout processing

## Data Transformation Details

### Content Structure
- Each chunk contains:
  - Content text
  - Source URL 
  - Page range information
  - Metadata including symbol, filename, document type, and timestamps
  - Content hash for deduplication

### Vector Storage
- Uses LanceDB for vector storage
- Each chunk is stored with its embedding and metadata
- Supports semantic search capabilities
- Maintains provenance information for all stored data

### Metadata Schema
The metadata schema includes:
- Symbol identifier
- Source filename and URL
- Document type classification  
- Processing timestamps
- Page range information
- Content hash for deduplication

## Configuration and Parameters

### Chunking Parameters
- Configurable chunk size and overlap
- Different strategies for different document types
- Semantic coherence preservation

### Embedding Parameters  
- Choice of embedding model
- Caching mechanism to avoid recomputation
- Vector dimensionality handling

## Error Handling and Robustness

### File-Level Errors
- Individual document failures don't stop processing of other documents
- Failed files are logged and tracked separately
- Manifest files record which files were successfully processed

### Stage-Level Errors  
- If any stage in the pipeline fails for a file, processing stops for that file
- Error messages are logged with full context
- No partial results are stored

### Resumability
- Manifest files track processed symbols
- Re-running pipeline skips already-processed items
- Incremental updates supported through careful state management