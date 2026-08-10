# Pipeline Architecture and Execution Flow

## Overview
The data pipeline follows a stage-based execution model with the following core stages:

1. **Document Collection** (`document_crawler`)
2. **Indexing** (`index`)

## Pipeline Execution Flow

### Stage 1: Document Collection (document_crawler)
- Reads company URLs from `config/company_urls.json`
- Uses `crawl4ai` to crawl web pages and discover document links
- Downloads PDFs, HTML, and other supported documents
- Creates manifest files with metadata about the crawl
- Stores documents in `data/raw/documents/{symbol}/`

### Stage 2: Indexing (index)
- Reads raw documents from `data/raw/documents/{symbol}/`
- Processes documents through the pipeline:
  - Type routing (determines document type)
  - Parsing (extracts content from documents)
  - Cleaning (removes noise and formats text)
  - Chunking (breaks content into manageable pieces)
  - Embedding (converts text to vectors)
  - Vector storage (stores embeddings in LanceDB)
- Stores processed results in vector database
- Metadata includes source URL, document type, and processing timestamps

## Orchestration Flow (main.py)
1. Parses command-line arguments (`--all-symbols`, `--symbol`, `--stage`)
2. Validates symbols against `config/company_urls.json`
3. Instantiates PipelineRunner
4. Executes stages in order for each symbol:
   - For each symbol, runs document_crawler first
   - Then runs index stage
5. Logs execution status and results
6. Returns summary of successful/failed symbols

## Key Design Decisions

### Atomic Processing
- Each file is processed atomically within the indexing stage
- If any step fails, the entire file processing is aborted
- Other files in the same symbol continue processing

### Resumability
- Manifest files mark symbols that have been attempted
- Re-running the pipeline skips already-processed symbols
- No duplicate processing of completed stages

### Error Handling
- Stage failures abort further downstream processing for that symbol
- Individual file failures don't affect other files in the same symbol
- Comprehensive logging for debugging and monitoring

### Configuration Management
- All paths defined in `config/settings.py`
- Consistent directory structure across all components
- Clear separation of raw, processed, and output data