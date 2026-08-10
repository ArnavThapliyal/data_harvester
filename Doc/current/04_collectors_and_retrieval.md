# Collectors and Retrieval System

## Overview
The retrieval system consists of two main data collection paths:
1. **Numeric Data Collection** - API-based collectors for structured financial data
2. **Document Data Collection** - Web crawler for unstructured company documents

## Numeric Collectors (Retrieval/Numeric/)

### Base Collector Interface
- `BaseNumericCollector` in `base_numeric_collector.py`
- Abstract base class defining the contract for all numeric collectors
- Provides common functionality for batch processing, error handling, and data export

### Implemented Collectors

#### YFinanceCollector (yfinance_collector.py)
- Collects financial data from Yahoo Finance
- Handles Indian stock symbols with proper `.NS` suffix
- Fetches OHLCV data, fundamental info, and financial statements
- Implements all required abstract methods from `BaseNumericCollector`

#### NSECollector (nse_collector.py)
- Skeleton implementation for NSE data collection
- Ready to be implemented with specific NSE API integration

#### BSCCollector (bsc_collector.py)
- Skeleton implementation for BSE data collection
- Ready to be implemented with specific BSE API integration

#### ScreenerCollector (screener_collector.py)
- Skeleton implementation for Screener.in data collection
- Ready to be implemented with specific Screener API integration

#### IndiaAPICollector (indiaapi_collector.py)
- Collects historical price data from India API
- Implements async request handling with retry logic
- Outputs per-symbol JSON files in `data/raw/`

### Collector Registry
- Located in `Retrieval/registry.py`
- Maintains mapping of collector names to their classes
- Provides `get_collector()` and `get_collectors()` functions
- Handles collector instantiation with proper parameters

## Document Collector (Retrieval/Document/document_crawler.py)

### Features
- Web crawler using `crawl4ai` for document discovery and download
- Rate limiting to respect target websites
- Multi-domain pacing (different delays for NSE, BSE, Screener)
- File type filtering and destination assignment
- Manifest file creation with download metadata
- Sanitized filename generation
- Download retry logic with exponential backoff

### Processing Flow
1. Reads company URLs from `config/company_urls.json`
2. For each seed URL:
   - Crawl the page using `crawl4ai`
   - Extract all internal and external links
   - Apply per-domain pacing delays
   - Filter downloadable files by extension
   - Download files to appropriate directories:
     - `data/raw/documents/{symbol}/` for processable documents
     - `data/raw/documents/other/{symbol}/` for other file types
3. Create manifest.json with metadata about the crawl process

### File Handling
- Supports multiple document types: PDF, HTML, Excel, CSV, PowerPoint, ZIP
- Processes ZIP files by extracting contents to temporary directory
- Sanitizes filenames to avoid filesystem issues
- Maintains source URL provenance for all downloaded files

## Data Storage Locations

### Raw Data
- `data/raw/numeric/` - Numeric data (JSON files per symbol)
- `data/raw/documents/` - Document data (files per symbol)  
- `data/raw/documents/other/` - Other file types (not processed)

### Manifest Files
- `data/raw/documents/{symbol}/manifest.json` - Metadata about document collection

## Configuration and Settings
- All paths defined in `config/settings.py`
- Configurable download directories for different file types
- Rate limiting and delay settings for web crawling