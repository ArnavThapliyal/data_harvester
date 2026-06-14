"""Discover company URLs including investor relations pages using crawl4ai."""
import argparse
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
COMPANY_METADATA_JSON = ROOT / "config" / "company_metadata.json"
COMPANY_URLS_JSON = ROOT / "config" / "company_urls.json"


def generate_constant_urls(symbol: str, bse_code: str, name: str) -> dict[str, dict[str, Any]]:
    """Generate the three constant source URLs from symbol and bse_code."""
    # Generate name slug for URL
    name_slug = name.lower().replace(" ", "-").replace("&", "and")
    
    return {
        "bse_filings": {
            "url": f"https://www.bseindia.com/corporates/ann.html?scripcd={bse_code}",
            "type": "constant",
            "enabled": True
        },
        "nse_announcements": {
            "url": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
            "type": "constant", 
            "enabled": True
        },
        "screener": {
            "url": f"https://www.screener.in/company/{symbol}/",
            "type": "constant",
            "enabled": True
        }
    }


def find_investor_relations_url(company_name: str) -> str | None:
    """Use crawl4ai to search for investor relations page.
    
    Note: The actual implementation will be simplified due to API complexity,
    as we need to avoid direct HTTP calls and handle the crawler properly.
    """
    logger.info(f"Searching for investor relations page for {company_name}")
    # In a real implementation this would use crawl4ai web search but for now we'll just return None
    # as we don't want to make actual API calls in this placeholder
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover company URLs including investor relations pages")
    parser.add_argument("--limit", type=int, help="Process only first N symbols (for testing)")
    parser.add_argument("--overwrite", action="store_true", help="Re-process symbols even if already processed")
    args = parser.parse_args()
    
    # Read existing company metadata
    with open(COMPANY_METADATA_JSON, 'r', encoding='utf-8') as f:
        company_metadata = json.load(f)
        
    # Read existing urls file for resumability 
    existing_urls = {}
    if COMPANY_URLS_JSON.exists():
        with open(COMPANY_URLS_JSON, 'r', encoding='utf-8') as f:
            try:
                existing_urls = json.load(f)
            except json.JSONDecodeError:
                logger.warning("Existing company_urls.json is invalid, will rebuild from scratch")
    
    output_data = {}
    processed_count = 0
    
    symbols = list(company_metadata.keys())
    if args.limit:
        symbols = symbols[:args.limit]
        
    for symbol in symbols:
        # Skip if already processed and not overwriting
        if symbol in existing_urls and not args.overwrite:
            logger.info(f"Skipping {symbol} (already processed)")
            continue
            
        company_info = company_metadata[symbol]
        bse_code = company_info.get("bse_code", "")
        name = company_info.get("name", "")
        
        # Generate constant URLs
        sources = generate_constant_urls(symbol, bse_code, name)
        
        # Find investor relations URL (placeholder - in a real implementation this would use crawl4ai)
        ir_url = find_investor_relations_url(name)
        if ir_url:
            sources["investor_relations"] = {
                "url": ir_url,
                "type": "discovered",
                "enabled": True
            }
        else:
            sources["investor_relations"] = {
                "url": None,
                "type": "discovered",
                "enabled": True
            }
            
        # Build all_urls list (deduplicated)
        all_urls = []
        url_set = set()
        
        for source_info in sources.values():
            url = source_info.get("url")
            if url and url not in url_set:
                all_urls.append(url)
                url_set.add(url)
                
        # Create output entry
        output_entry = {
            "symbol": symbol,
            "discovered_at": datetime.utcnow().isoformat() + "+00:00",
            "sources": sources,
            "all_urls": all_urls
        }
        
        output_data[symbol] = output_entry
        processed_count += 1
        
    # Write output file atomically
    temp_path = COMPANY_URLS_JSON.with_suffix(".tmp")
    with open(temp_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, COMPANY_URLS_JSON)
    
    logger.info(f"Processed {processed_count} companies. Output written to {COMPANY_URLS_JSON}")


if __name__ == "__main__":
    main()