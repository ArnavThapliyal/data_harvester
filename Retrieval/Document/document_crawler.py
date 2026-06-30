"""
Unified document crawler for downloading files from company URLs using fallback approach.
This implementation combines the best practices from company_crawler and document_crawler.
"""

import argparse
import json
import logging
import os
import time
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import urllib.parse

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# Import config settings to know where to put files
from config.settings import (
    RAW_DOCUMENTS,
    RAW_DOCUMENTS_OTHER,
    COMPANY_URLS_JSON
)

logger = logging.getLogger(__name__)

# File extensions that should be processed by the pipeline
PROCESSABLE_EXTENSIONS = {
    ".pdf", ".html", ".htm", ".xlsx", ".xls", ".csv", ".pptx", ".ppt", ".doc", ".docx", ".zip"
}

# File extensions that go to "other" directory without further processing  
OTHER_EXTENSIONS = {
    ".mp3", ".mp4", ".avi", ".mov", ".wav"
}

def run(symbol: str) -> dict:
    """Entry point for pipeline.py to process a single company."""
    # TODO: Load COMPANY_URLS_JSON, extract "all_urls", and pass to process_single_company
    pass

async def process_single_company(symbol: str, urls: List[str], overwrite: bool = False) -> dict:
    """
    Process downloads for a single company.
    Returns a status dict: {"status": "success"|"failed"|"no_data"|"skipped"}
    """
    # TODO: Implement modern AsyncWebCrawler logic here
    pass
                                                                                                                                                                                                                                                                                                       
def main():
    """Main entry point for document crawler."""
    parser = argparse.ArgumentParser(description="Download documents from company URLs")
    parser.add_argument("--symbols", help="Comma-separated list of symbols to process (all by default)")
    parser.add_argument("--limit", type=int, help="Limit number of symbols to process")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing downloads")
    
    args = parser.parse_args()
    
    # Read company urls
    try:
        with open(COMPANY_URLS_JSON, 'r') as f:
            company_urls = json.load(f)
    except Exception as e:
        logger.error(f"Failed to read company URLs file: {e}")
        return
        
    # Filter symbols if specified
    if args.symbols:
        symbols = [s.strip().upper() for s in args.symbols.split(',')]
        company_urls = {s: v for s, v in company_urls.items() if s in symbols}
        
    if args.limit:
        company_urls = dict(list(company_urls.items())[:args.limit])
        
    # Process each symbol
    for symbol, urls in company_urls.items():
        logger.info(f"Starting processing for symbol: {symbol}")
        process_single_company(symbol, urls, overwrite=args.overwrite)


if __name__ == "__main__":
    main()