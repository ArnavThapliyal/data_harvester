# Storage and Output Structure

## Overview
The system uses a structured storage approach with distinct directories for each stage of the pipeline and final outputs. All data directories are git-ignored to avoid committing large datasets.

## Data Storage Structure

### Raw Data Directories
```
data/
├── raw/
│   ├── numeric/              # Numeric data (JSON files per symbol)
│   ├── documents/            # Document data (files per symbol)
│   │   ├── {symbol}/         # Per-symbol document directory
│   │   │   ├── manifest.json # Crawl metadata
│   │   │   └── *.pdf, *.html, etc. # Downloaded documents
│   │   └── other/            # Other file types (not processed)
│   └── done/                 # Processed symbols marker
```

### Processed Data Directories  
```
data/
├── cleaned/                  # Post-cleaner output
│   └── {symbol}/             # Per-symbol cleaned data
├── chunked/                  # Post-chunker output  
│   └── {symbol}/             # Per-symbol chunked data
└── exports/                  # Final export files (not yet implemented)
```

## Vector Storage

### LanceDB Integration
- Vector embeddings are stored in LanceDB database
- Each symbol's data is stored in a separate table or dataset
- Supports semantic search and retrieval operations
- Maintains metadata alongside embeddings

### Storage Schema
Each vector entry contains:
- Content text
- Vector embedding (numeric array)
- Metadata fields (symbol, source_url, filename, document_type, timestamp)
- Content hash for deduplication

## Manifest and Tracking Files

### Document Crawler Manifest
Generated in `data/raw/documents/{symbol}/manifest.json`:
```json
{
  "symbol": "TCS",
  "source_urls": ["https://www.bseindia.com/corporates/ann.html?scripcd=123456"],
  "crawler_used": "crawl4ai",
  "links_found": 15,
  "downloaded_files": [
    {
      "url": "https://example.com/annual-report.pdf",
      "file": "/data/raw/documents/TCS/annual-report.pdf",
      "success": true,
      "error": null,
      "doc_type": "processable"
    }
  ],
  "timestamp": "2026-06-04T18:32:15.640435+00:00",
  "status": "completed"
}
```

### Processing State Tracking
- Manifest files mark symbols that have been attempted
- Re-running pipeline skips already-processed symbols
- No duplicate processing of completed stages

## Output Format (Planned)

### Final Knowledge Files
The ultimate goal is to generate per-symbol markdown knowledge files containing:
- All collected financial data
- All processed document content  
- Source provenance information
- Semantic search indexes

### Export Formats (Planned)
- Markdown documents with embedded metadata
- JSON representations for programmatic access
- Vector databases for semantic search

## Directory Management

### Automatic Creation
All required directories are automatically created on import via `config/settings.py`:
- Raw data directories
- Processed data directories  
- Vector storage locations

### Git Ignore
All data directories are in `.gitignore`:
```
data/raw/
data/cleaned/
data/chunked/
data/exports/
data/done/
```

## Data Flow and Dependencies

### Processing Dependencies
1. **Document Collection** → **Indexing**: Requires raw documents to exist
2. **Indexing** → **Final Output**: Requires completed indexing to generate knowledge files

### State Management
- Each stage maintains its own directory structure
- Files are processed in order and tracked through the pipeline
- Intermediate results are stored for resumability

## Data Security and Privacy

### Git Safety
- All data directories are git-ignored to prevent accidental commits
- Sensitive API keys and credentials are stored in `.env` (not committed)
- No sensitive data is stored in the repository

### Data Integrity
- Manifest files provide tracking of processing state
- Content hashes ensure data consistency
- Atomic operations prevent partial writes