# data_harvester — Complete Pipeline Implementation Guide

> Hand this document to your coding agent as-is. Every module, its inputs, outputs,
> internal logic, and connection to the next stage are fully specified. Do not deviate
> from folder paths, filenames, or output schemas — downstream modules depend on them exactly.

---

## Pipeline Overview

```
LOOP (runs until stopped)
│
├─ 1. Source
│     build_universe.py → company_universe.csv + company_metadata.json
│
├─ 2. URL Discovery
│     url_discovery.py → config/company_urls.json
│
├─ 3. Retrieval (two parallel paths)
│     ├─ Numeric:   API collectors   → data/raw/numeric/{SYMBOL}.json
│     └─ Document:  document_collector.py → data/raw/documents/{SYMBOL}/
│
├─ 4. Converter (two parallel paths)
│     ├─ Numeric:   numeric_flattener.py  → data/trans/numeric/{SYMBOL}.json
│     └─ Document:  file_extractor.py     → data/trans/documents/{SYMBOL}/*.txt
│
├─ 5. Cleaner (called separately for each path)
│     ├─ Numeric:   cleaner.py(mode=numeric)   → data/cleaned/numeric/{SYMBOL}.json
│     └─ Document:  cleaner.py(mode=document)  → data/cleaned/documents/{SYMBOL}/*.txt
│
├─ 6. Chunker
│     chunker.py → data/chunked/{SYMBOL}/*.chunks.json
│
├─ 7. Normalizer
│     normalizer.py → data/done/{SYMBOL}_Numerical.md
│                  → data/done/{SYMBOL}_Document.md
│
└─ SLEEP → repeat from step 2
```

---

## Dependencies to add to pyproject.toml

```toml
dependencies = [
    "httpx>=0.28.1",
    "pandas>=3.0.3",
    "pyarrow>=19.0.0",
    "pyyaml>=6.0.3",
    "tenacity>=9.1.4",
    "yfinance>=1.4.1",
    "beautifulsoup4>=4.12",
    "pypdf>=4.0",
    "crawl4ai>=0.4.0",
    "tqdm>=4.66",
    "python-dotenv>=1.0",
]
```

---

## Directory Structure Changes Required

Create these directories before any code runs:

```
data/raw/numeric/           ← numeric JSON output (was data/raw/ flat)
data/raw/documents/         ← downloaded files per symbol
data/raw/documents/other/   ← unsupported extensions (mp3, mp4, etc.)
data/trans/numeric/         ← flattened numeric JSON
data/trans/documents/       ← extracted text from documents
data/cleaned/numeric/       ← cleaned numeric JSON
data/cleaned/documents/     ← cleaned document text
data/chunked/               ← chunks per symbol
data/done/                  ← final markdown files
```

Add a helper to `config/settings.py` that creates all of these on import:

```python
for d in [RAW_NUMERIC, RAW_DOCUMENTS, TRANS_NUMERIC, TRANS_DOCUMENTS,
          CLEANED_NUMERIC, CLEANED_DOCUMENTS, CHUNKED, DONE]:
    d.mkdir(parents=True, exist_ok=True)
```

---

## Module 1 — `scripts/build_universe.py` (extend existing)

**Already works.** Add one new responsibility: after writing `company_universe.csv`,
also write `config/company_metadata.json`.

**Output schema for `company_metadata.json`:**

```json
{
  "RELIANCE": {
    "symbol": "RELIANCE",
    "isin": "INE002A01018",
    "bse_code": "500325",
    "name": "Reliance Industries Limited",
    "industry": "Oil & Gas",
    "market_cap_category": "Large",
    "index": "NiftyMidSmallcap400",
    "urls": {
      "bse_corp": "https://www.bseindia.com/stock-share-price/reliance-industries-ltd/RELIANCE/500325/",
      "nse_equity": "https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE",
      "screener": "https://www.screener.in/company/RELIANCE/",
      "investor_relations": null,
      "annual_reports": null
    },
    "metadata_updated_at": "2026-06-12T11:36:00+05:30"
  }
}
```

**Rules:**

- `bse_corp`, `nse_equity`, `screener` are always generated from `symbol` and `bse_code` — no HTTP.
- `investor_relations` and `annual_reports` are always `null` here; `url_discovery.py` populates them.
- Write atomically: write to `.tmp` then `os.replace()`.

---

## Module 2 — `scripts/url_discovery.py` (new file)

**Purpose:** Discover all URLs associated with every company and write them to
`config/company_urls.json`. This script runs rarely — only when you want to refresh
the source list. It does not download anything.

**Input:** `config/company_metadata.json`
**Output:** `config/company_urls.json`

### Output schema

```json
{
  "RELIANCE": {
    "symbol": "RELIANCE",
    "discovered_at": "ISO8601",
    "sources": {
      "bse_filings": {
        "url": "https://www.bseindia.com/corporates/ann.html?scripcd=500325",
        "type": "constant",
        "enabled": true
      },
      "nse_announcements": {
        "url": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
        "type": "constant",
        "enabled": true
      },
      "screener": {
        "url": "https://www.screener.in/company/RELIANCE/",
        "type": "constant",
        "enabled": true
      },
      "investor_relations": {
        "url": "https://www.ril.com/investor-relations",
        "type": "discovered",
        "enabled": true
      }
    },
    "all_urls": [
      "https://...",
      "https://..."
    ]
  }
}
```

### Internal logic

```
class URLDiscovery:

    CONSTANT_SOURCES = {
        "bse_filings":       lambda symbol, bse_code: f"https://www.bseindia.com/corporates/ann.html?scripcd={bse_code}",
        "nse_announcements": lambda symbol, bse_code: f"https://www.nseindia.com/companies-listing/corporate-filings-announcements",
        "screener":          lambda symbol, bse_code: f"https://www.screener.in/company/{symbol}/",
    }

    def get_constant_urls(self, symbol, bse_code) -> dict:
        # generates all constant source URLs deterministically from symbol + bse_code
        # no HTTP calls

    def discover_investor_relations(self, symbol, company_name) -> str | None:
        # uses crawl4ai to search for the company investor relations page
        # search query: "{company_name} investor relations annual report site:*.com"
        # return the first result that looks like an official IR page
        # heuristic: URL contains "investor", "ir.", "shareholders", "annual-report"
        # if nothing found, return None — do not guess

    def run(self, overwrite: bool = False):
        # for each symbol in company_metadata.json:
        #   1. generate constant URLs
        #   2. call discover_investor_relations (skip if already in company_urls.json and not overwrite)
        #   3. merge into sources dict
        #   4. build flat all_urls list (deduplicated)
        # write config/company_urls.json atomically
        # log: [url_discovery] SYMBOL — found N urls (K constant, M discovered)
```

**Rate limit:** 3 seconds between crawl4ai calls during discovery.
**Resumable:** if `company_urls.json` already has an entry for a symbol and `--overwrite` is
not set, skip that symbol.

---

## Module 3 — `Retrieval/Document/document_collector.py` (new file)

**Purpose:** For every company, crawl every URL in `company_urls.json`, discover all
downloadable files, and download them.

**Input:** `config/company_urls.json`
**Output:** `data/raw/documents/{SYMBOL}/` with all files + `manifest.json`

### Supported and unsupported extensions

```python
DOWNLOAD_EXTENSIONS = {
    "documents": [".pdf", ".html", ".htm", ".xlsx", ".xls", ".csv", ".pptx", ".ppt", ".doc", ".docx", ".zip"],
    "other":     [".mp3", ".mp4", ".avi", ".mov", ".wav", ".zip"]  # saved separately, not processed
}
```

Files with extensions in `other` go to `data/raw/documents/other/{SYMBOL}/` — downloaded and
stored for future processing, no further pipeline action now.

Files with no recognized extension: log and skip, do not download.

### Crawler logic

```
class DocumentCollector:

    def __init__(self):
        self.crawl4ai_crawler = AsyncWebCrawler()   # crawl4ai
        self.httpx_client = httpx.Client(timeout=30, follow_redirects=True)

    def crawl_url(self, url: str) -> list[dict]:
        # PRIMARY: try crawl4ai first — handles JS-rendered pages
        # returns list of {href, link_text, content_type}
        # if crawl4ai fails or returns empty links: fallback to httpx + BeautifulSoup
        # log which crawler was used per URL

    def is_downloadable(self, url: str, link_text: str) -> tuple[bool, str]:
        # returns (should_download, bucket)
        # bucket = "documents" or "other"
        # logic: check URL extension first
        #        if no extension, check Content-Type header with a HEAD request
        #        HEAD request timeout = 5s; if it fails, skip

    def download_file(self, url: str, dest_dir: Path) -> dict:
        # streams file to dest_dir using httpx
        # filename: sanitize from URL, max 200 chars, no special chars except _ - .
        # if filename collision: append _2, _3 etc.
        # write atomically: stream to .tmp then rename
        # returns {url, filename, success, size_bytes, error, downloaded_at}

    def run(self, symbols: list[str] | None = None, overwrite: bool = False):
        # for each symbol:
        #   1. load URLs from company_urls.json
        #   2. for each URL: crawl → discover links → filter downloadable → download
        #   3. write data/raw/documents/{SYMBOL}/manifest.json
        #   4. log progress: [document_collector] [SYMBOL] [n/N] url — K files downloaded
```

### Manifest schema (`data/raw/documents/{SYMBOL}/manifest.json`)

```json
{
  "symbol": "RELIANCE",
  "last_run": "ISO8601",
  "total_files": 12,
  "sources": [
    {
      "source_url": "https://www.bseindia.com/...",
      "crawled_at": "ISO8601",
      "crawler_used": "crawl4ai",
      "links_found": 34,
      "files_downloaded": [
        {
          "url": "https://...",
          "filename": "annual_report_2024.pdf",
          "size_bytes": 4823012,
          "downloaded_at": "ISO8601",
          "success": true,
          "error": null
        }
      ]
    }
  ]
}
```

**Resumability:** Check manifest before downloading. If a file with the same URL exists in
manifest with `success: true`, skip unless `--overwrite`.

---

## Module 4 — Converter (two separate scripts)

### 4A — `converter/numeric_flattener.py`

**Input:** `data/raw/numeric/{SYMBOL}.json` (from any numeric collector)
**Output:** `data/trans/numeric/{SYMBOL}.json`

```python
def flatten(src: Path, dest: Path) -> dict:
    # reads raw collector JSON
    # normalizes into:
    {
      "symbol": "RELIANCE",
      "source": "indiaapi",
      "fetched_at": "ISO8601",
      "ohlcv": [
        {"date": "YYYY-MM-DD", "open": 0.0, "high": 0.0, "low": 0.0, "close": 0.0, "volume": 0}
      ],
      "fundamentals": {
        "pe_ratio": null,
        "pb_ratio": null,
        "market_cap": null,
        "dividend_yield": null,
        "52w_high": null,
        "52w_low": null
      }
    }
    # missing fields → null, never raise
    # write atomically
```

Different collectors use different field names. Map them:

- IndiaAPI: `date`, `open`, `high`, `low`, `close`, `volume` (check actual response)
- YFinance: `Date`, `Open`, `High`, `Low`, `Close`, `Volume`
- NSE: check actual response shape when implementing
- BSE: check actual response shape when implementing

### 4B — `converter/file_extractor.py`

**Input:** `data/raw/documents/{SYMBOL}/` (all downloaded files)
**Output:** `data/trans/documents/{SYMBOL}/` (one `.txt` per file, plus `index.json`)

```python
class FileExtractor:

    def extract_pdf(self, src: Path, dest: Path) -> dict:
        # uses pypdf
        # extracts text page by page
        # inserts page boundary markers: \n\n--- PAGE 1 ---\n\n
        # if PDF is encrypted: write empty .txt + log warning, do not raise
        # returns {pages, char_count, success, error}

    def extract_html(self, src: Path, dest: Path) -> dict:
        # uses BeautifulSoup
        # removes: <script>, <style>, <nav>, <header>, <footer>, <aside>
        # extracts remaining text preserving paragraph breaks
        # returns {char_count, success, error}

    def extract_zip(self, src: Path, extract_dir: Path) -> list[Path]:
        # safely unzip (guard zip-slip: check all paths resolve inside extract_dir)
        # recurse into extracted files using extract_file()
        # max depth 2
        # returns list of newly extracted file paths

    def extract_office(self, src: Path, dest: Path) -> dict:
        # for .xlsx, .xls: use pandas to read all sheets, convert to CSV-like text
        # for .pptx, .ppt, .docx, .doc: extract text from each slide/page
        # use python-pptx for pptx, python-docx for docx (add to pyproject.toml)
        # returns {success, error}

    def extract_file(self, src: Path, dest_dir: Path) -> dict:
        # dispatcher: calls the right extractor based on suffix
        # .pdf → extract_pdf
        # .html/.htm → extract_html
        # .zip → extract_zip
        # .xlsx/.xls/.pptx/.ppt/.docx/.doc → extract_office
        # .csv → copy as-is (already text)
        # unknown → log and skip

    def run(self, symbol: str, overwrite: bool = False):
        # processes all files in data/raw/documents/{SYMBOL}/
        # skips files in other/ subdirectory
        # writes extracted text to data/trans/documents/{SYMBOL}/
        # writes data/trans/documents/{SYMBOL}/index.json:
        {
          "symbol": "RELIANCE",
          "extracted_at": "ISO8601",
          "files": [
            {
              "original": "annual_report_2024.pdf",
              "extracted": "annual_report_2024.txt",
              "extractor": "pdf",
              "char_count": 84231,
              "pages": 120,
              "success": true,
              "error": null,
              "source_url": "https://..."   ← copied from manifest.json
            }
          ]
        }
```

**Source URL traceability:** When building `index.json`, look up each filename in
`data/raw/documents/{SYMBOL}/manifest.json` to find its original URL. This URL must travel
all the way to the final markdown.

---

## Module 5 — `pipeline/cleaner.py` (called twice, separate modes)

**Called once for numeric, once for documents. Same file, different mode argument.**

```python
class Cleaner:

    def clean_numeric(self, src: Path, dest: Path) -> None:
        # input: data/trans/numeric/{SYMBOL}.json
        # output: data/cleaned/numeric/{SYMBOL}.json
        # operations:
        # - remove OHLCV rows where close <= 0 or date is null
        # - deduplicate by date (keep last)
        # - sort by date ascending
        # - null out fundamentals fields that are 0 (0 P/E means missing, not zero)
        # - validate all dates parse as YYYY-MM-DD

    def clean_text(self, text: str) -> str:
        # used by clean_document for each extracted .txt file
        # operations (in order):
        # 1. normalize unicode: unicodedata.normalize("NFKC", text)
        # 2. remove null bytes and non-printable chars (keep \n and \t)
        # 3. collapse 3+ consecutive blank lines → max 2 blank lines
        # 4. strip common PDF noise patterns:
        #    - lines matching r"^Page \d+ of \d+$"
        #    - lines matching r"^CONFIDENTIAL$" or r"^Draft$" (case-insensitive)
        #    - lines that are only dashes, underscores, or dots (5+ chars)
        # 5. do NOT remove numbers, section headers, or financial figures

    def clean_document(self, src_dir: Path, dest_dir: Path) -> None:
        # input: data/trans/documents/{SYMBOL}/
        # output: data/cleaned/documents/{SYMBOL}/
        # for each .txt file: apply clean_text, write to dest_dir with same filename
        # copy index.json from src_dir to dest_dir unchanged (metadata travels through)

    def run(self, symbol: str, mode: str) -> None:
        # mode = "numeric" or "document"
        # dispatches to clean_numeric or clean_document accordingly
        # log: [cleaner] [SYMBOL] mode=numeric|document — done
```

---

## Module 6 — `pipeline/chunker.py`

**Input:** `data/cleaned/documents/{SYMBOL}/*.txt` + `data/cleaned/numeric/{SYMBOL}.json`
**Output:** `data/chunked/{SYMBOL}/` — one `.chunks.json` per source file

```python
class Chunker:

    TEXT_CHUNK_SIZE    = 1500   # characters
    TEXT_CHUNK_OVERLAP = 200    # characters

    def chunk_text(self, text: str, symbol: str, source_file: str, source_url: str) -> list[dict]:
        # splits on sentence boundaries: re.split(r'(?<=[.!?।])\s+', text)
        # builds chunks of TEXT_CHUNK_SIZE with TEXT_CHUNK_OVERLAP overlap
        # each chunk:
        {
          "chunk_id": "RELIANCE_annual_report_2024_003",
          "symbol": "RELIANCE",
          "source_file": "annual_report_2024.txt",
          "source_url": "https://...",      ← from index.json, must be preserved
          "chunk_index": 3,
          "total_chunks": 47,
          "text": "...",
          "char_start": 4200,
          "char_end": 5700,
          "chunk_type": "document"
        }

    def chunk_numeric(self, data: dict, symbol: str) -> list[dict]:
        # numeric data is not split into text chunks
        # instead produce one chunk per 90-day window of OHLCV data
        # each chunk:
        {
          "chunk_id": "RELIANCE_numeric_indiaapi_2024Q1",
          "symbol": "RELIANCE",
          "source_file": "RELIANCE.json",
          "source_url": null,
          "chunk_index": 0,
          "total_chunks": 12,
          "text": "RELIANCE price data 2024-01-01 to 2024-03-31:\nDate | Open | High | Low | Close | Volume\n...",
          "chunk_type": "numeric",
          "period_start": "2024-01-01",
          "period_end": "2024-03-31"
        }

    def run(self, symbol: str) -> None:
        # 1. for each .txt in data/cleaned/documents/{SYMBOL}/ → chunk_text
        #    look up source_url from data/cleaned/documents/{SYMBOL}/index.json
        # 2. for data/cleaned/numeric/{SYMBOL}.json → chunk_numeric
        # 3. write each result to data/chunked/{SYMBOL}/{source_file}.chunks.json
        # log: [chunker] [SYMBOL] — N text chunks + M numeric chunks
```

---

## Module 7 — `pipeline/normalizer.py` — two output files

**Input:** `data/chunked/{SYMBOL}/` + `data/cleaned/numeric/{SYMBOL}.json` + `config/company_metadata.json`
**Output:**

- `data/done/{SYMBOL}_Numerical.md`
- `data/done/{SYMBOL}_Document.md`

### 7A — `{SYMBOL}_Numerical.md` structure

```markdown
# RELIANCE — Reliance Industries Limited

## Company Metadata
| Field | Value |
|---|---|
| Symbol | RELIANCE |
| ISIN | INE002A01018 |
| BSE Code | 500325 |
| Industry | Oil & Gas |
| Market Cap Category | Large Cap |
| Index | NiftyMidSmallcap400 |

## Price History (Last 60 Trading Days)
| Date | Open | High | Low | Close | Volume |
|---|---|---|---|---|---|
| 2026-06-12 | 1420.00 | 1435.50 | 1415.00 | 1431.20 | 8234000 |
...

## Price Statistics
| Metric | Value |
|---|---|
| 52-Week High | ... |
| 52-Week Low | ... |
| Current Price | ... |

## Fundamentals
| Metric | Value |
|---|---|
| P/E Ratio | ... |
| P/B Ratio | ... |
| Dividend Yield | ... |
| Market Cap | ... |

## Data Sources
| Source | Fetched At |
|---|---|
| IndiaAPI | 2026-06-12T... |
| NSE | 2026-06-12T... |

---
*Generated: ISO8601 | Symbol: RELIANCE*
```

### 7B — `{SYMBOL}_Document.md` structure

```markdown
# RELIANCE — Document Intelligence

## Company Overview
Name: Reliance Industries Limited | Symbol: RELIANCE

## Collected Documents
| File | Source URL | Downloaded | Size |
|---|---|---|---|
| annual_report_2024.pdf | https://... | 2026-06-12 | 4.8 MB |
| q3_transcript.pdf | https://... | 2026-06-12 | 1.2 MB |
...

---

## annual_report_2024.pdf
> Source: https://...  |  Downloaded: 2026-06-12  |  Pages: 120

### Chunk 1 / 47
[chunk text here, ~1500 chars]

---
### Chunk 2 / 47
[chunk text here]

---
[... all chunks ...]

---

## q3_transcript.pdf
> Source: https://...  |  Downloaded: 2026-06-12

### Chunk 1 / 12
[chunk text here]

---
[... all chunks ...]

---
*Generated: ISO8601 | Symbol: RELIANCE | Total chunks: 284*
```

**Rules for normalizer:**

- Only include a document section if it has at least one successful chunk.
- Documents with `success: false` in index.json → add to "Collected Documents" table with
a `⚠ extraction failed` note, but do not create a content section for them.
- Numeric file: if `data/cleaned/numeric/{SYMBOL}.json` does not exist, write Numerical.md
with a single line `*No numeric data collected for this symbol.`*
- Write atomically.
- Log: `[normalizer] [SYMBOL] — Numerical.md (N lines) + Document.md (M lines)`

---

## Module 8 — `main.py` — Continuous Orchestrator

**Replaces current placeholder entirely.**

```python
def run_symbol(symbol: str, stages: list[str], overwrite: bool) -> None:
    # runs all requested stages for a single symbol in order

def run_pipeline(
    symbols: list[str] | None = None,   # None = all from company_universe.csv
    stages: list[str] | None = None,    # None = all stages
    overwrite: bool = False,
    limit: int | None = None,
    loop: bool = False,                 # True = run continuously until stopped
    loop_interval_hours: int = 24,      # how long to sleep between full runs
) -> None:
    # Stage execution order:
    # "source"    → scripts/build_universe.py logic
    # "discover"  → scripts/url_discovery.py logic
    # "numeric"   → all NUMERIC_COLLECTORS
    # "document"  → DocumentCollector
    # "convert"   → FileExtractor + NumericFlattener
    # "clean"     → Cleaner (numeric mode) + Cleaner (document mode)
    # "chunk"     → Chunker
    # "normalize" → Normalizer
    #
    # if loop=True: after completing all symbols, sleep loop_interval_hours, then restart from "discover"
    # (skip "source" on re-runs unless --refresh-universe flag passed)
```

**CLI:**

```bash
# Full pipeline, all 400 symbols, run once
python main.py

# Full pipeline, loop forever, re-run every 24 hours
python main.py --loop --loop-interval 24

# Test on 5 symbols
python main.py --limit 5

# Specific symbols only
python main.py --symbols RELIANCE TCS HDFCBANK

# Specific stages only
python main.py --stages discover document convert clean chunk normalize

# Force re-download everything
python main.py --overwrite

# Skip URL discovery (use existing company_urls.json)
python main.py --stages numeric document convert clean chunk normalize
```

**Logging:** All output goes to both stdout and `data/pipeline.log`.
Format: `[2026-06-12T11:36:00] [STAGE] [SYMBOL] STATUS — message`
Statuses: `START`, `SKIP`, `DONE`, `FAIL`, `WARN`

**Resumability rule (applies to every stage):**
Before running a stage for a symbol, check if its output already exists.
If yes and `--overwrite` not set: log `SKIP — output exists` and move on.
This means any interrupted run can be resumed by re-running the same command.

---

## Retrieval/registry.py — rewrite

```python
from Retrieval.Numeric.indiaapi_collector import IndiaAPICollector
from Retrieval.Numeric.nse_collector import NSECollector
from Retrieval.Numeric.bse_collector import BSECollector
from Retrieval.Numeric.yfinance_collector import YFinanceCollector
from Retrieval.Document.document_collector import DocumentCollector

NUMERIC_COLLECTORS = {
    "indiaapi": IndiaAPICollector,
    "nse":      NSECollector,
    "bse":      BSECollector,
    "yfinance": YFinanceCollector,
}

DOCUMENT_COLLECTORS = {
    "document": DocumentCollector,
}

def get_numeric_collector(name: str):
    if name not in NUMERIC_COLLECTORS:
        raise ValueError(f"Unknown numeric collector: {name}. Available: {list(NUMERIC_COLLECTORS)}")
    return NUMERIC_COLLECTORS[name]()

def get_document_collector(name: str):
    if name not in DOCUMENT_COLLECTORS:
        raise ValueError(f"Unknown document collector: {name}. Available: {list(DOCUMENT_COLLECTORS)}")
    return DOCUMENT_COLLECTORS[name]()
```

Wrap each import in try/except so an unimplemented collector does not crash the registry.

---

## Implementation Sequence

Build strictly in this order. Do not skip ahead — each phase produces outputs the next one reads.

```
Step 1   config/settings.py          → add all path constants + auto-mkdir
Step 2   scripts/build_universe.py   → add company_metadata.json output
Step 3   scripts/url_discovery.py    → constant URLs first, then crawl4ai discovery
Step 4   Retrieval/Numeric/          → verify base, implement NSE → BSE → YFinance
Step 5   Retrieval/Document/         → document_collector.py (crawl4ai + httpx fallback)
Step 6   converter/numeric_flattener.py
Step 7   converter/file_extractor.py
Step 8   pipeline/cleaner.py
Step 9   pipeline/chunker.py
Step 10  pipeline/normalizer.py
Step 11  Retrieval/registry.py
Step 12  main.py
```

---

## Verification Checkpoints

Run these checks after each step before continuing.


| After Step | Command                                                     | Expected Result                                                                                 |
| ---------- | ----------------------------------------------------------- | ----------------------------------------------------------------------------------------------- |
| 2          | `python scripts/build_universe.py`                          | `config/company_metadata.json` exists, ≥ 400 keys, every entry has `urls` dict                  |
| 3          | `python scripts/url_discovery.py --limit 3`                 | `config/company_urls.json` with 3 entries, each has `all_urls` list ≥ 3 items                   |
| 4          | `python -m Retrieval.Numeric.indiaapi_collector --limit 2`  | `data/raw/numeric/RELIANCE.json` with `success: true`                                           |
| 5          | `python -m Retrieval.Document.document_collector --limit 1` | `data/raw/documents/RELIANCE/` with ≥ 1 file + `manifest.json`                                  |
| 6          | Run flattener on step 4 output                              | `data/trans/numeric/RELIANCE.json` has `ohlcv` array                                            |
| 7          | Run extractor on step 5 output                              | `data/trans/documents/RELIANCE/` has ≥ 1 `.txt` + `index.json`                                  |
| 8          | Run cleaner on both modes                                   | `data/cleaned/numeric/` and `data/cleaned/documents/` both non-empty                            |
| 9          | Run chunker                                                 | `data/chunked/RELIANCE/` has `.chunks.json` files, each chunk has `source_url`                  |
| 10         | Run normalizer                                              | `data/done/RELIANCE_Numerical.md` and `data/done/RELIANCE_Document.md` both render cleanly      |
| 12         | `python main.py --limit 2 --loop false`                     | Full pipeline completes for 2 symbols, no uncaught exceptions, both `.md` files in `data/done/` |


