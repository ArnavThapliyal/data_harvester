# Entry Points and Orchestration

## Main Entry Point (main.py)

### Overview
The `main.py` file serves as the central orchestrator for the entire pipeline, providing a consistent interface for running the data harvesting process.

### Command Line Interface
```bash
# Process all symbols with all stages
python main.py --all-symbols

# Process a single symbol with all stages  
python main.py --symbol TCS

# Process a single symbol with only one stage
python main.py --symbol TCS --stage index

# Help information
python main.py --help
```

### Argument Validation
The orchestrator performs strict validation:
- `--all-symbols` and `--symbol` are mutually exclusive
- `--stage` can only be used with `--symbol`
- Symbols must exist in `config/company_urls.json`

### Logging and Monitoring
Comprehensive logging system:
- UTC timestamps for all log entries
- Both file and console output
- Detailed status information for each symbol and stage
- Error context and stack traces when failures occur

## Pipeline Runner (pipeline/pipeline.py)

### Core Functionality
The `PipelineRunner` class orchestrates the execution flow:

1. **Stage Selection**: Determines which stages to run based on command-line arguments
2. **Symbol Processing**: Iterates through symbols in the configured order  
3. **Stage Execution**: Runs each stage for each symbol in proper sequence
4. **Error Handling**: Gracefully handles failures and continues with remaining symbols
5. **Result Tracking**: Maintains lists of succeeded and failed symbols

### Error Propagation
- If a stage fails for any symbol, that symbol is marked as failed
- Downstream stages are skipped for failed symbols  
- Individual file-level failures don't affect other files in the same symbol

### Status Reporting
The pipeline provides detailed summary information:
- Total symbols processed
- Number of successful and failed symbols
- Failed symbol names for easy debugging

## Stage Execution Flow

### Document Collection Stage (document_crawler)
1. Reads symbol URLs from `config/company_urls.json`
2. Uses `crawl4ai` to crawl seed URLs  
3. Discovers and downloads documents from discovered links
4. Creates manifest files with download metadata
5. Stores documents in `data/raw/documents/` directory

### Indexing Stage (index)
1. Reads raw documents from `data/raw/documents/{symbol}/`
2. Processes each document through the pipeline:
   - Type routing to determine processing approach
   - Parsing to extract content  
   - Cleaning to remove noise and normalize text
   - Chunking to break content into semantic units
   - Embedding to convert text to vectors
   - Vector storage in LanceDB with metadata
3. Returns metadata about files processed, failed, or skipped

## Execution Dependencies and State Management

### Symbol-Level Dependencies
- `document_crawler` must complete before `index` can run for any symbol
- Each symbol is processed independently (parallel execution)
- Manifest files provide state tracking between runs

### Stage-Level Dependencies  
- Stage execution follows strict ordering in `STAGE_ORDER`
- Each stage operates on the output from the previous stage
- Intermediate results are not persisted to disk (except manifest files)

### Resumability Features
- Manifest files mark symbols that have been attempted
- Re-running pipeline skips already-processed symbols  
- No duplicate processing of completed stages

## Integration Points

### Data Flow Integration
```
config/company_urls.json → document_crawler → data/raw/documents/{symbol}/
                                    ↓
                              index → LanceDB vectors
```

### Metadata Integration
- All stages maintain metadata about their operations
- Source URLs are preserved throughout the pipeline  
- Timestamps and processing information are tracked

## Testing and Validation

### Test Coverage
Minimal tests exist in `tests/test_yfinance_api_.py` for basic functionality testing.

### Validation Checks
- Input parameter validation
- Symbol existence verification  
- File system access permissions
- API key availability for collectors that require them

## Performance Considerations

### Concurrency Management
- Each symbol processes independently in its own execution context
- Web crawling has built-in rate limiting for target sites
- Parallel processing of different symbols is supported

### Resource Management
- Memory usage is optimized through in-memory pipeline stages  
- Temporary directories are cleaned up after processing
- Vector storage uses efficient LanceDB format

## Future Extension Points

### Pipeline Expansion
- Additional stages can be added to `STAGE_ORDER` as needed
- New collector types can be registered in the registry
- Custom processing stages can be implemented

### Configuration Extensibility  
- Command-line options can be extended for additional features
- Pipeline parameters can be made configurable via config files
- Stage-specific settings can be added to support varied processing needs