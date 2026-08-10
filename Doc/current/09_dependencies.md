# Dependencies and External Services

## Overview
The data harvester system relies on several external dependencies and services for its core functionality. These include Python packages, web services, and database systems.

## Core Python Dependencies

### Main Dependencies (from pyproject.toml)
```toml
[project.dependencies]
beautifulsoup4>=4.14.3      # HTML/XML parsing
crawl4ai>=0.8.9            # Web crawling and content extraction
docling>=2.109.0           # Document processing
flagembedding>=1.4.0       # Embedding models
httpx>=0.28.1              # HTTP client for API requests
lancedb>=0.34.0            # Vector database storage  
langchain-text-splitters>=1.1.2  # Text chunking
pandas>=3.0.3              # Data processing
pdfplumber>=0.11.10        # PDF content extraction
pyarrow>=19.0.0            # Data processing
pypdf>=6.13.2              # PDF handling
pypdf2>=3.0.1              # PDF processing
python-docx>=1.2.0         # Word document handling
python-magic>=0.4.27       # File type detection
python-pptx>=1.0.2         # PowerPoint handling
pyyaml>=6.0.3              # YAML processing
sentence-transformers>=5.6.0  # Text embedding
tenacity>=9.1.4            # Retry logic
torch>=2.12.1              # Deep learning framework for embeddings  
yfinance>=1.4.1            # Yahoo Finance API access
```

### Development Dependencies
```toml
[project.optional-dependencies.dev]
pytest>=9.0.3              # Testing framework
ruff>=0.15.15              # Code formatting and linting
python-pptx>=0.6.21        # Additional PowerPoint support
python-docx>=1.1.0         # Additional Word document support
```

## External Services and APIs

### Web Crawling Service (crawl4ai)
- **Purpose**: Web page crawling and content extraction
- **Usage**: Used by `document_crawler.py` to discover and download documents
- **Rate Limiting**: Built-in support for rate limiting to respect target sites
- **Features**: Handles JavaScript-rendered content, link discovery, and content extraction

### Financial Data APIs

#### Yahoo Finance (yfinance)
- **Purpose**: Financial data collection for Indian stocks
- **Usage**: `yfinance_collector.py` 
- **Features**: OHLCV data, fundamental information, financial statements
- **Rate Limits**: No built-in limits, requires careful pacing to avoid blocking

#### India API (indiaapi_collector.py)
- **Purpose**: Historical price and financial data collection  
- **Usage**: `indiaapi_collector.py`
- **Features**: Async request handling with retry logic
- **Requirements**: API key needed (stored in environment variables)

### Document Processing Services

#### PDF Processing
- **pdfplumber**: Extracts text and structure from PDF files
- **pypdf**: Alternative PDF handling capabilities  
- **python-magic**: Detects file types for proper processing

#### Document Format Support
- **pypdf2**: Advanced PDF operations
- **python-docx**: Word document handling
- **python-pptx**: PowerPoint presentation handling

## Vector Database Integration (LanceDB)

### Purpose
- **Storage**: Persistent storage for vector embeddings
- **Search**: Semantic search capabilities for document retrieval  
- **Integration**: Part of the indexing pipeline in `indexer.py`

### Features
- Efficient vector storage with built-in indexing
- Support for semantic similarity searches  
- Schema flexibility to accommodate different document types

## Infrastructure Dependencies

### System Requirements
```bash
# Required system packages (from README)
brew install xz
brew install libmagic
```

### Python Environment
- **Version**: 3.11.9 (as specified in `.python-version`)
- **Package Manager**: uv (as mentioned in README)
- **Virtual Environment**: Created and managed via `uv venv --python 3.11.9`

## Configuration Requirements

### Environment Variables
Required for API access:
```
INDIA_API_KEY=your_api_key_here
# Additional API keys as needed for collectors that require them
```

### Configuration Files
- `config/company_universe.csv`: Main company universe (400+ symbols)
- `config/company_urls.json`: URLs for each company (not yet generated)  
- `config/settings.py`: Path configuration and directory setup

## Dependency Management

### Package Installation
```bash
# Using uv (as recommended in README)
uv venv --python 3.11.9
uv sync
```

### Package Verification
The system includes:
- Dependency validation in the orchestrator  
- Graceful handling of missing dependencies
- Error messages indicating what packages are needed

## Known Issues and Limitations

### Dependency Issues
1. **Import Path Changes**: Some modules had import paths changed from `collectors.*` to `Retrieval.Numeric.*`
2. **Stale Dependencies**: Some packages may be outdated or have compatibility issues
3. **Missing Package Support**: Some specialized document types may lack proper handling

### External Service Limitations
1. **Rate Limiting**: Web crawling and API access have rate limits that must be respected
2. **API Availability**: Some APIs may not be accessible from all network environments  
3. **Data Quality**: External data sources may have inconsistent quality or formatting

## Future Dependency Considerations

### Potential Additions
1. **Enhanced Web Crawling**: More robust content extraction capabilities  
2. **Advanced NLP Models**: Better document understanding and categorization
3. **Cloud Storage Integration**: For larger-scale data storage solutions

### Version Management
- Regular updates to dependency versions for security and feature improvements
- Compatibility testing across different Python versions  
- Automated dependency validation during CI/CD processes

## Integration Points

### Service Integration
The system integrates with external services through:
- HTTP APIs for data collection (Yahoo Finance, India API)
- Web scraping for document discovery and download
- Vector databases for semantic search capabilities

### Data Flow Integration  
```
External API → Raw Data Storage → Processing Pipeline → Vector Database
Web Crawler → Document Storage → Processing Pipeline → Vector Database
```

## Security and Compliance Considerations

### API Key Management
- API keys are stored in environment variables (not committed to source)
- The system validates that required keys are present before running collectors

### Web Access Compliance
- Built-in rate limiting to respect target websites
- Proper user-agent headers for web requests  
- Compliance with robots.txt and terms of service where applicable