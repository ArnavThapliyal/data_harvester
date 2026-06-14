"""Build company_universe.csv from a Nifty index constituent list."""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "ind_NiftyMidSmallcap4005050_list.csv"
DEFAULT_OUTPUT = ROOT / "config" / "company_universe.csv"
DEFAULT_METADATA_OUTPUT = ROOT / "config" / "company_metadata.json"

INDEX_NAME = "nifty_midsmallcap400"
MARKET_CAP_CATEGORY = "mid_small_cap"

OUTPUT_COLUMNS = [
    "ticker",
    "isin",
    "bse_code",
    "name",
    "industry",
    "series",
    "market_cap_category",
    "index",
]

SOURCE_TO_OUTPUT = {
    "Symbol": "ticker",
    "ISIN Code": "isin",
    "Company Name": "name",
    "Industry": "industry",
    "Series": "series",
}


def build_universe(source: Path, output: Path) -> int:
    with source.open(newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        missing = set(SOURCE_TO_OUTPUT) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"source CSV missing columns: {sorted(missing)}")

        rows = []
        for row in reader:
            symbol = (row.get("Symbol") or "").strip()
            if not symbol:
                continue
            rows.append(
                {
                    "ticker": symbol,
                    "isin": (row.get("ISIN Code") or "").strip(),
                    "bse_code": (row.get("BSE Code") or "").strip(),  # Fixed typo to match actual column name
                    "name": (row.get("Company Name") or "").strip(),
                    "industry": (row.get("Industry") or "").strip(),
                    "series": (row.get("Series") or "").strip(),
                    "market_cap_category": MARKET_CAP_CATEGORY,
                    "index": INDEX_NAME,
                }
            )

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    # Also build company metadata JSON
    metadata = {}
    current_timestamp = datetime.utcnow().isoformat() + "+00:00"
    
    for row in rows:
        symbol = row["ticker"]
        
        # Generate URLs deterministically from symbol and bse_code
        bse_code = row["bse_code"] 
        # Handle empty bse_code case gracefully
        bse_url_part = bse_code if bse_code else ""
        name_slug = row["name"].lower().replace(" ", "-").replace("&", "and")
        
        # Create URL components from symbol and bse_code
        metadata[symbol] = {
            "symbol": symbol,
            "isin": row["isin"],
            "bse_code": bse_code,
            "name": row["name"],
            "industry": row["industry"],
            "market_cap_category": row["market_cap_category"],
            "index": row["index"],
            "urls": {
                "bse_corp": f"https://www.bseindia.com/stock-share-price/{name_slug}/{symbol}/{bse_url_part}/",
                "nse_equity": f"https://www.nseindia.com/get-quotes/equity?symbol={symbol}",
                "screener": f"https://www.screener.in/company/{symbol}/",
                "investor_relations": None,
                "annual_reports": None
            },
            "metadata_updated_at": current_timestamp
        }
    
    # Write metadata file atomically 
    metadata_output = DEFAULT_METADATA_OUTPUT
    temp_path = metadata_output.with_suffix(".tmp")
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, metadata_output)

    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Nifty constituent CSV (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"company universe CSV (default: {DEFAULT_OUTPUT})",
    )
    args = parser.parse_args()

    if not args.source.is_file():
        raise SystemExit(f"source file not found: {args.source}")

    count = build_universe(args.source, args.output)
    print(f"Wrote {count} companies to {args.output}")
    print(f"Wrote metadata for {count} companies to {DEFAULT_METADATA_OUTPUT}")


if __name__ == "__main__":
    main()
