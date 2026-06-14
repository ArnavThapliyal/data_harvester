# Cursor Prompt — base_collector.py

 file `base_collector.py` implementing an abstract base class for financial data collectors. Follow every requirement below exactly — do not add extra methods, do not remove any specified methods, do not change the class hierarchy.

---

## Class: `BaseCollector` (ABC)

### Required class-level attributes (defined by child, not base)
Every child class MUST define these as class-level constants:
- `SOURCE_NAME: str`
- `BASE_URL: str`
- `BATCH_SIZE: int`
- `MAX_RETRIES: int`
- `OUTPUT_COLUMNS: list[str]`

---

### Abstract Methods (child must implement all four)

```
build_request(self, batch: list[str]) -> any
    # Returns a fully constructed request object/dict for a batch of symbols

fetch_batch(self, request: any) -> any
    # Sends the request; returns raw response

parse_response(self, response: any) -> list[dict]
    # Parses raw response into a list of raw record dicts

normalize_record(self, record: dict) -> dict
    # Maps one raw record dict into the internal standard format
```

---

### Concrete Methods (implemented in BaseCollector, not overridden)

#### `run(self) -> None`
Top-level pipeline orchestrator. Calls in this exact order:
1. `read_symbols()`
2. `create_batches()`
3. `execute_batch()` for each batch
4. `collect_results()`
5. `normalize_dataset()`
6. `clean_dataset()`
7. `export_csv()`
8. `export_parquet()`

---

#### `read_symbols(self) -> list[dict]`
Input: `company_universe.csv`
CSV fields: `symbol`, `company_name`, `exchange`, `isin`, `sector`, `industry`

Steps:
- Open file
- Read rows
- Parse CSV
- Extract symbols
- Extract metadata (all fields per row)
- Remove rows where symbol is empty
- Remove duplicate symbols (keep first)
- Create symbol list
- Create batches (call `create_batches()`)

Returns: list of symbol strings e.g. `["RELIANCE", "TCS", "INFY"]`

---

#### `create_batches(self, symbols: list[str]) -> list[list[str]]`
- Split symbol list into chunks of size `BATCH_SIZE`
- Returns list of batches

---

#### `execute_batch(self, batch: list[str]) -> any`
Per batch:
- Call `build_request(batch)` → request object
- Call `fetch_batch(request)` → raw response
- Track response codes
- Track request timing
- Manage rate limits (respect delays between requests)
- On failure: call `retry_request()`
- On final failure: call `handle_failure()`
- Returns raw response or None on complete failure

---

#### `retry_request(self, batch: list[str], attempt: int) -> any`
- Retry the full execute flow for a batch
- Retry up to `MAX_RETRIES` attempts
- Handle:
  - Timeout errors
  - Connection errors
  - HTTP errors
  - API errors
- Exponential backoff between retries
- Returns response on success or raises after max retries

---

#### `handle_failure(self, batch: list[str], error: Exception) -> None`
- Catch exceptions
- Catch timeout errors
- Catch connection errors
- Catch HTTP errors
- Catch API errors
- Record failed symbols
- Log failures (include symbol list, error type, error message)
- Skip invalid responses
- Store failure information (in `self.failed_symbols: list` and `self.failure_log: list[dict]`)

---

#### `collect_results(self, responses: list[any]) -> list[dict]`
Input: list of raw responses (successful only)

Steps:
- Parse JSON from each response
- Parse API response structure
- Extract fields
- Extract nested fields
- Merge responses from multiple batches
- Combine batches into one collection
- Aggregate records
- Track missing symbols (symbols with no returned data)
- Track collected symbols
- Build dataset

Returns: combined raw dataset as `list[dict]`

---

#### `normalize_dataset(self, raw_records: list[dict]) -> list[dict]`
- Call `normalize_record()` on each record
- Returns list of normalized dicts

---

#### `clean_dataset(self, records: list[dict]) -> pd.DataFrame`
Steps:
- Rename columns to standard names
- Standardize field names
- Convert strings to numbers (where applicable)
- Convert strings to dates (where applicable)
- Convert timestamps
- Normalize symbols (uppercase, strip whitespace)
- Normalize exchange names
- Normalize currencies
- Handle null values
- Handle missing values
- Remove duplicates
- Drop invalid rows
- Validate required fields (raise or log if missing)
- Validate schema against `OUTPUT_COLUMNS`
- Reorder columns to match `OUTPUT_COLUMNS`
- Create derived fields (if any column computation is needed)

Returns: `pd.DataFrame`

---

#### `export_csv(self, df: pd.DataFrame) -> None`
- Create output path
- Create filename (include `SOURCE_NAME` and current date)
- Create output directories if they don't exist
- Write CSV
- Support append or overwrite mode
- Optionally compress output
- Verify output file exists after write
- Generate export metadata (row count, columns, timestamp)
- Generate export summary (log to console or file)

---

#### `export_parquet(self, df: pd.DataFrame) -> None`
- Create output path
- Create filename (include `SOURCE_NAME` and current date)
- Create output directories if they don't exist
- Write Parquet
- Support append or overwrite mode
- Optionally compress output
- Verify output file exists after write
- Generate export metadata (row count, columns, timestamp)
- Generate export summary (log to console or file)

---

## State attributes on `self` (initialized in `__init__`)
- `self.symbols: list[str]` — populated by `read_symbols()`
- `self.batches: list[list[str]]` — populated by `create_batches()`
- `self.failed_symbols: list[str]` — populated by `handle_failure()`
- `self.failure_log: list[dict]` — populated by `handle_failure()`
- `self.collected_symbols: list[str]` — populated by `collect_results()`
- `self.missing_symbols: list[str]` — populated by `collect_results()`
- `self.raw_records: list[dict]` — populated by `collect_results()`
- `self.output_df: pd.DataFrame` — populated by `clean_dataset()`

---

## Validation
- After `clean_dataset()`, check all numeric fields for negative values — log a warning if any negative values are found (do not silently drop unless explicitly invalid)
- Validate schema: DataFrame columns must match `OUTPUT_COLUMNS` exactly before export

---

## Monitoring / observability (tracked on self, logged at end of `run()`)
- Total requests made
- Total failures
- Last successful run timestamp
- API downtime events (any batch where all retries failed)

---

## Minimal child class example (include as a docstring or comment, NOT as runnable code):
```python
class NSECollector(BaseCollector):
    SOURCE_NAME = "NSE"
    BASE_URL = "https://..."
    BATCH_SIZE = 50
    MAX_RETRIES = 3
    OUTPUT_COLUMNS = [...]

    def build_request(self, batch): ...
    def fetch_batch(self, request): ...
    def parse_response(self, response): ...
    def normalize_record(self, record): ...
```

---

## Imports allowed
`abc`, `csv`, `logging`, `os`, `pathlib`, `datetime`, `time`, `pandas`, `requests` (or `httpx`), `json`, `typing`

No other third-party libraries unless required by the above spec.
