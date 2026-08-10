# Directory Structure

## Root Files and Directories

```
data_harvester/
├── main.py                          # Continuous orchestrator (complete)
├── config/                          # Configuration files
│   ├── company_universe.csv         # Live universe (~400 symbols)
│   ├── company_metadata.json        # Company metadata and URLs (in progress)
│   ├── settings.py                  # Path constants
│   └── sources/                     # Nifty constituent CSVs
├── scripts/                         # Utility scripts
│   └── build_universe.py            # Universe CSV builder
├── pipeline/                        # Converter processing chain (complete)
│   ├── cleaner.py                   # Complete implementation
│   ├── chunker.py                   # Complete implementation
│   ├── embedder.py                  # Complete implementation
│   ├── normalizer.py                # Complete implementation
│   ├── indexer.py                   # Indexer for document processing
│   ├── type_router.py               # File type routing
│   ├── parser.py                    # Document parsing
│   ├── vector_store.py              # Vector database integration
│   └── __init__.py                  # Pipeline namespace
├── Retrieval/                       # Data collection components
│   ├── Numeric/                     # API-based numeric collectors
│   │   ├── base_numeric_collector.py # Abstract base class
│   │   ├── indiaapi_collector.py     # India API collector (working)
│   │   ├── yfinance_collector.py     # YFinance collector (complete)
│   │   ├── nse_collector.py          # NSE collector (skeleton)
│   │   ├── bsc_collector.py          # BSC collector (skeleton)
│   │   ├── screener_collector.py     # Screener collector (skeleton)
│   │   └── registry.py               # Collector registry
│   ├── Document/                    # Web document crawler
│   │   └── document_crawler.py       # Complete crawler implementation
│   ├── transcript_collector.py      # Placeholder
│   └── __init__.py                  # Retrieval namespace
├── storage/                         # Storage components (stale)
│   └── raw_store.py                 # Stale placeholder
├── data/                            # Data storage directories (gitignored)
│   ├── raw/                         # Raw collected data
│   ├── cleaned/                     # Post-cleaner output
│   ├── chunked/                     # Post-chunker output
│   ├── exports/                     # Final exports
│   └── done/                        # Processed symbols
├── tests/                           # Test files
│   └── test_yfinance_api_.py        # Minimal tests
├── Doc/                             # Documentation
│   └── current/                     # Current documentation
└── pyproject.toml                   # Project dependencies
```

## Key Directories and Their Purposes

### config/
- Contains configuration files including company universe CSV and settings
- `company_universe.csv`: Main list of ~400 companies with symbol information
- `company_metadata.json`: Company URLs and metadata (not yet generated)
- `settings.py`: Path constants for all data directories

### pipeline/
- Core processing pipeline components
- Contains the converter chain: cleaner → chunker → embedder → normalizer
- Indexer module that handles document processing from raw to vector store

### Retrieval/
- Data collection components
- Numeric collectors for API-based financial data
- Document crawler for web scraping company documents

### data/
- Git-ignored directories for storing processed data
- Raw data from collection
- Cleaned, chunked, and exported outputs

### tests/
- Minimal test coverage for existing components