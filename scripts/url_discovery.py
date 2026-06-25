import argparse
import json
import logging
import os
import sys
import datetime
from pathlib import Path

import pandas as pd


# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def load_universe(csv_path: Path) -> list[dict]:
    """Load company universe from CSV and filter out invalid BSE codes."""
    try:
        df = pd.read_csv(csv_path)
        logger.info(f"Columns in CSV: {df.columns.tolist()}")
    except Exception as e:
        logger.error(f"Failed to read CSV file {csv_path}: {e}")
        sys.exit(1)

    # Identify symbol and BSE code columns
    symbol_col = None
    bse_col = None
    name_col = None

    for col in df.columns:
        if col.lower() in ('symbol', 'ticker'):
            symbol_col = col
        elif col.lower() in ('bse_code', 'bse code'):
            bse_col = col
        elif col.lower() == 'company_name':
            name_col = col

    if not symbol_col or not bse_col:
        logger.error(f"Could not find required columns. Found columns: {df.columns.tolist()}")
        sys.exit(1)

    # Filter out rows where BSE code is blank, non-numeric, or 'Unlisted'
    def is_valid_bse_code(code, symbol):
        if pd.isna(code) or str(code).strip() == '':
            logger.info(f"Filtering out row with blank BSE code for symbol '{symbol}'")
            return False
        if str(code).lower().strip() == 'unlisted':
            logger.info(f"Filtering out row with 'Unlisted' BSE code for symbol '{symbol}'")
            return False
        try:
            int(code)
            return True
        except ValueError:
            logger.info(f"Filtering out row with non-numeric BSE code '{code}' for symbol '{symbol}'")
            return False

    df_filtered = df[df.apply(lambda row: is_valid_bse_code(row[bse_col], row[symbol_col]), axis=1)].copy()
    df_filtered[symbol_col] = df_filtered[symbol_col].astype(str).str.strip()
    df_filtered[bse_col] = df_filtered[bse_col].astype(int).astype(str)

    # Convert to list of dicts
    universe = []
    for _, row in df_filtered.iterrows():
        universe.append({
            "symbol": row[symbol_col],
            "bse_code": row[bse_col],
            "name": row.get(name_col, "") if name_col else ""
        })

    total_rows = len(df)
    filtered_rows = total_rows - len(df_filtered)
    processed_rows = len(df_filtered)
    logger.info(f"Filtered out {filtered_rows} of {total_rows} rows; processing {processed_rows}")
    
    return universe


def build_source_urls(symbol: str, bse_code: str) -> dict:
    """Generate source URLs for a given symbol and BSE code."""
    return {
        "bse_filings": {
            "url": f"https://www.bseindia.com/corporates/ann.html?scripcd={bse_code}",
            "category": "regulatory_filings",
            "enabled": True
        },
        "nse_announcements": {
            "url": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
            "category": "regulatory_filings",
            "enabled": True
        },
        "screener_standalone": {
            "url": f"https://www.screener.in/company/{symbol}/",
            "category": "financial_documents",
            "enabled": True
        },
        "screener_consolidated": {
            "url": f"https://www.screener.in/company/{symbol}/consolidated/",
            "category": "financial_documents",
            "enabled": True
        },
        "bse_insider_trading": {
            "url": f"https://www.bseindia.com/stock-share-price/stockreach_insidertrade.aspx?scripcode={bse_code}",
            "category": "market_shareholding",
            "enabled": True
        }
    }


def discover_urls_for_symbol(company: dict) -> dict:
    """Discover URLs for a single company symbol."""
    symbol = company["symbol"]
    bse_code = company["bse_code"]
    discovered_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    sources = build_source_urls(symbol, bse_code)

    # Extract just the URLs and deduplicate while preserving order
    seen = set()
    all_urls = []
    for source in sources.values():
        url = source["url"]
        if url not in seen:
            seen.add(url)
            all_urls.append(url)

    return {
        "symbol": symbol,
        "discovered_at": discovered_at,
        "sources": sources,
        "all_urls": all_urls
    }


def load_existing_urls(json_path: Path) -> dict:
    """Load existing URLs from JSON file."""
    if not json_path.exists():
        return {}

    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.warning(f"Failed to load existing URLs from {json_path}: {e}")
        return {}


def write_urls_atomic(data: dict, json_path: Path) -> None:
    """Atomically write URLs to JSON file."""
    tmp_path = json_path.with_suffix(json_path.suffix + '.tmp')
    try:
        with open(tmp_path, 'w') as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, json_path)
    except Exception as e:
        logger.error(f"Failed to write URLs to {json_path}: {e}")
        raise


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Discover company URLs for data collection."
    )
    parser.add_argument("--limit", type=int, help="Limit the number of symbols to process.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing URLs.")
    parser.add_argument("--symbols", nargs="+", help="Specific symbols to process.")

    args = parser.parse_args()

    csv_path = Path("config/company_universe.csv")
    json_path = Path("config/company_urls.json")

    universe = load_universe(csv_path)
    existing_urls = load_existing_urls(json_path)

    updated_data = existing_urls.copy()
    processed_count = 0

    for company in universe:
        symbol = company["symbol"]
        
        # Skip if already exists and not overwriting
        if symbol in updated_data and not args.overwrite:
            continue
        
        # If --symbols specified, only process those
        if args.symbols and symbol not in args.symbols:
            continue
            
        processed_count += 1
        result = discover_urls_for_symbol(company)
        updated_data[symbol] = result

        if args.limit and processed_count >= args.limit:
            break

    write_urls_atomic(updated_data, json_path)
    logger.info("URL discovery and writing complete.")


if __name__ == "__main__":
    main()