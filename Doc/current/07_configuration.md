# Configuration and Schemas

## Overview
The system uses a comprehensive configuration approach with centralized settings, environment variables, and structured data schemas.

## Configuration Files

### config/settings.py
Central configuration file that defines all paths and directory structures:

```python
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CONFIG_DIR = BASE_DIR / "config"
RAW_NUMERIC = BASE_DIR / "data" / "raw" / "numeric"
RAW_DOCUMENTS = BASE_DIR / "data" / "raw" / "documents"
RAW_DOCUMENTS_OTHER = BASE_DIR / "data" / "raw" / "documents" / "other"
TRANS_NUMERIC = BASE_DIR / "data" / "transient" / "numeric"
TRANS_DOCUMENTS = BASE_DIR / "data" / "transient" / "documents"
CLEANED_NUMERIC = BASE_DIR / "data" / "cleaned" / "numeric"
CLEANED_DOCUMENTS = BASE_DIR / "data" / "cleaned" / "documents"
CHUNKED = BASE_DIR / "data" / "chunked"
DONE = BASE_DIR / "data" / "done"
COMPANY_UNIVERSE_CSV = CONFIG_DIR / "company_universe.csv"
COMPANY_METADATA_JSON = CONFIG_DIR / "company_metadata.json"
COMPANY_URLS_JSON = CONFIG_DIR / "company_urls.json"

# Ensure all directories are created on import
for path in [
    RAW_NUMERIC,
    RAW_DOCUMENTS,
    RAW_DOCUMENTS_OTHER,
    TRANS_NUMERIC,
    TRANS_DOCUMENTS,
    CLEANED_NUMERIC,
    CLEANED_DOCUMENTS,
    CHUNKED,
    DONE,
]:
    path.mkdir(parents=True, exist_ok=True)
```

### config/company_universe.csv
The main company universe file containing:
- Symbol identifiers (note: column header is "Syobol" with typo)
- BSE codes for web crawling
- Company names and other metadata

### config/company_urls.json
Company metadata file that will contain:
- URLs for each company's document sources
- Metadata about data sources and categories

## Environment Variables

### API Keys and Credentials
The system relies on environment variables for sensitive data:

```
INDIA_API_KEY=your_api_key_here
# Additional API keys as needed for various collectors
```

### Configuration Parameters
- `PYTHONPATH` - Set to include project root for imports
- `UV_PYTHON` - Set to Python 3.11.9 as specified in project requirements

## Data Schemas

### Numeric Collector Output Schema
Defined in `BaseNumericCollector` and implemented by child classes:

```python
OUTPUT_COLUMNS = [
    "symbol",
    "company_name", 
    "exchange",
    "isin",
    "sector",
    "industry",
    "market_cap",
    "pe_ratio",
    "price_earnings_growth",
    "dividend_yield",
    "beta",
    "52_week_high",
    "52_week_low",
    "volume",
    "avg_volume_3_month",
    "open_price",
    "close_price",
    "high_price",
    "low_price",
    "timestamp",
]
```

### Document Metadata Schema
```json
{
  "source_url": "https://example.com/document.pdf",
  "page_range": "1-25", 
  "symbol": "TCS",
  "source_filename": "annual-report.pdf",
  "doc_type": "annual_report",
  "downloaded_at": "2026-06-04T18:32:15.640435+00:00",
  "section_path": "/reports/annual"
}
```

## Pipeline Configuration

### Stage Ordering
The pipeline stages are defined in `pipeline/pipeline.py`:

```python
STAGE_ORDER = [
    "document_crawler",
    "index",
]
```

### Command Line Arguments
The main entry point supports:
- `--all-symbols`: Process all symbols in company_urls.json
- `--symbol SYM`: Process a single symbol  
- `--stage STAGE`: Run only one specific stage

## Validation and Error Handling

### Input Validation
- Symbols must exist in `config/company_urls.json`  
- Required configuration files must be present
- API keys must be set for collectors that require them

### Schema Validation
- Each stage's output is validated against expected schemas
- Metadata consistency checks are performed
- Error logging provides clear failure information

## Configuration Best Practices

### Environment Management
- Use `.env` files for local development configurations
- Do not commit sensitive credentials to version control
- Use environment variable validation in entry points

### Path Management
- All paths are defined relative to project root for portability
- Directory creation is handled automatically on import
- Path constants ensure consistency across modules

### Version Control Considerations
- Configuration files are committed to version control
- Data directories are git-ignored to prevent accidental commits
- Environment variable documentation is maintained in README