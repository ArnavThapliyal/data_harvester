"""
Unified document crawler for downloading files from company URLs using fallback approach.
This implementation combines the best practices from company_crawler and document_crawler.
"""
import httpx
import shutil
import argparse
import json
import logging
import os
import time
import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, urljoin
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
    """Sync entry point for pipeline.py — wraps the async implementation."""
    return asyncio.run(_run_async(symbol))

async def _run_async(symbol: str) -> dict:
    try:
        with open(COMPANY_URLS_JSON, 'r') as f:
            company_urls = json.load(f)
    except Exception as e:
        logger.error(f"[DocumentCrawler] [{symbol}] failed to load company_urls.json: {e}")
        return {"status": "failed"}

    entry = company_urls.get(symbol)
    if not entry:
        logger.warning(f"[DocumentCrawler] [{symbol}] no entry in company_urls.json")
        return {"status": "no_data"}

    urls = entry.get("all_urls", [])
    if not urls:
        logger.warning(f"[DocumentCrawler] [{symbol}] all_urls is empty")
        return {"status": "no_data"}

    return await process_single_company(symbol, urls)

async def process_single_company(symbol: str, urls: List[str], overwrite: bool = False) -> dict:
    manifest_path = RAW_DOCUMENTS / symbol / "manifest.json"

    if not overwrite and manifest_path.exists():
        logger.info(f"[DocumentCrawler] [{symbol}] skipping — manifest exists")
        return {"status": "skipped"}

    (RAW_DOCUMENTS / symbol).mkdir(parents=True, exist_ok=True)
    (RAW_DOCUMENTS_OTHER / symbol).mkdir(parents=True, exist_ok=True)

    all_downloaded = []  # list of dicts from download_file()

    browser_config = BrowserConfig(headless=True)
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=30000,
        delay_before_return_html=2.0,   # lets NSE JS tables populate
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in urls:
            logger.info(f"[DocumentCrawler] [{symbol}] fetching seed URL: {url}")

            try:
                result = await crawler.arun(url=url, config=run_config)
            except Exception as e:
                logger.warning(f"[DocumentCrawler] [{symbol}] crawl exception for {url}: {e}")
                continue

            if not result.success:
                logger.warning(f"[DocumentCrawler] [{symbol}] crawl failed for {url}: {result.error_message}")
                continue

            # result.links["internal"] and result.links["external"] are already
            # absolute, DOM-resolved URLs — no relative-URL fix-up needed
            raw_links = (
                result.links.get("internal", []) +
                result.links.get("external", [])
            )
            hrefs = [item["href"] for item in raw_links if item.get("href")]
            logger.info(f"[DocumentCrawler] [{symbol}] {len(hrefs)} links found on {url}")

            for href in hrefs:
                doc_type, dest_dir = determine_download_destination(href, symbol)
                if doc_type == "skip":
                    continue

                filename = sanitize_filename(href)
                dest_path = dest_dir / filename

                if dest_path.exists() and not overwrite:
                    logger.debug(f"[DocumentCrawler] [{symbol}] already exists, skipping: {filename}")
                    continue

                success, error, final_path = download_file(href, dest_path, symbol)
                all_downloaded.append({
                    "url": href,
                    "file": str(final_path) if final_path else None,
                    "success": success,
                    "error": error,
                    "doc_type": doc_type
                })

                if success:
                    logger.info(f"[DocumentCrawler] [{symbol}] downloaded: {filename}")
                else:
                    logger.warning(f"[DocumentCrawler] [{symbol}] failed to download {href}: {error}")

            await asyncio.sleep(0.5)   # courteous delay between seed URLs

    # Derive status
    if not all_downloaded:
        status = "no_data"
    elif any(f["success"] for f in all_downloaded):
        status = "success"
    else:
        status = "failed"

    # Write manifest regardless of status — marks this symbol as attempted
    manifest = create_manifest(
        symbol=symbol,
        source_urls=urls,
        crawler_used="crawl4ai",
        links_found=len(all_downloaded),
        downloaded_files=all_downloaded
    )
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    files_ok = sum(1 for f in all_downloaded if f["success"])
    logger.info(f"[DocumentCrawler] [{symbol}] done — status={status}, downloaded={files_ok}/{len(all_downloaded)}")
    return {"status": status, "files_downloaded": files_ok}
                                                                                                                                                                                                                                                                                                       
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
        
    # Fix 1: schema bug — extract all_urls from the nested object
    for symbol, entry in company_urls.items():
        urls = entry.get("all_urls", [])          # NOT entry itself
        logger.info(f"Starting processing for symbol: {symbol}")
        asyncio.run(process_single_company(symbol, urls, overwrite=args.overwrite))  # Fix 2: await the async fn

if __name__ == "__main__":
    main()