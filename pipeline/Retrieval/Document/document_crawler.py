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
from typing import List, Optional, Dict, Any, Tuple
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

# Domain-specific rate limiting settings (in seconds)
DOMAIN_RATE_LIMITS = {
    'nseindia.com': 2.5,
    'bseindia.com': 2.5,
    'screener.in': 1.5
}

# Global state for domain rate limiting
_domain_locks: Dict[str, asyncio.Lock] = {}
_last_accessed: Dict[str, float] = {}

def get_file_extension(url: str) -> str:
    """Extract file extension from URL."""
    parsed_url = urlparse(url)
    path = parsed_url.path
    if not path:
        return ""
    return os.path.splitext(path)[1].lower()

def is_url_downloadable(url: str) -> bool:
    """Check if a URL points to a downloadable file."""
    # Check if it's an actual downloadable file based on extension
    ext = get_file_extension(url)
    
    # If no extension, check content type
    if not ext:
        return False
        
    return ext in PROCESSABLE_EXTENSIONS or ext in OTHER_EXTENSIONS

def sanitize_filename(url: str) -> str:
    """Safely convert URL to a filename."""
    parsed_url = urlparse(url)
    path = parsed_url.path
    
    # Replace problematic characters with underscores
    filename = os.path.basename(path)
    
    # If no basename, try to use the URL as-is but sanitize it
    if not filename or filename == '/':
        filename = url.replace("http://", "").replace("https://", "").replace("/", "_")
        
    # Sanitize filename characters  
    sanitized = "".join(c for c in filename if c.isalnum() or c in "._- ")
    
    # If the result is empty, use a default name
    return sanitized if sanitized else f"file_{int(time.time())}"

def determine_download_destination(url: str, symbol: str) -> Tuple[str, Path]:
    """Determine download directory based on URL extension."""
    ext = get_file_extension(url)
    
    # Check if it's a directly downloadable file or needs to be skipped
    if not is_url_downloadable(url):
        return "skip", RAW_DOCUMENTS / symbol

    if ext in PROCESSABLE_EXTENSIONS:
        return "processable", RAW_DOCUMENTS / symbol
    elif ext in OTHER_EXTENSIONS:
        return "other", RAW_DOCUMENTS_OTHER / symbol
    else:
        # Default to processable for unknown extensions
        return "processable", RAW_DOCUMENTS / symbol 

async def download_file(url: str, dest_path: Path, symbol: str) -> Tuple[bool, Optional[str], Optional[Path]]:
    """Download file from URL and save to destination."""
    for attempt in range(3):  # Maximum 3 attempts
        try:
            # Add a timeout and headers for better downloads
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, follow_redirects=True, timeout=30.0, headers=headers)
                response.raise_for_status()
                
                # Write to file
                with open(dest_path, 'wb') as f:
                    f.write(response.content)
                    
                logger.debug(f"[DocumentCrawler] [{symbol}] downloaded: {dest_path.name}")
                return True, None, dest_path
                
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (429, 503):
                retry_after = e.response.headers.get('Retry-After')
                if retry_after:
                    # Parse Retry-After header
                    try:
                        wait_time = int(retry_after)
                    except ValueError:
                        wait_time = 2  # Default to 2s if parsing fails
                else:
                    # Exponential backoff: 2s, 4s, 8s
                    wait_time = 2 ** attempt
                    
                logger.warning(f"[DocumentCrawler] [{symbol}] rate limited for {url}, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
            else:
                logger.warning(f"[DocumentCrawler] [{symbol}] failed to download {url}: {e}")
                return False, str(e), None
        except Exception as e:
            logger.warning(f"[DocumentCrawler] [{symbol}] unexpected error downloading {url}: {e}")
            return False, str(e), None
    
    # If we get here, all 3 attempts failed
    logger.error(f"[DocumentCrawler] [{symbol}] failed after retries: {url}")
    return False, "Rate limited/Failed after retries", None

def create_manifest(symbol: str, source_urls: List[str], crawler_used: str, 
                   links_found: int, downloaded_files: List[Dict]) -> Dict[str, Any]:
    """Create manifest file with metadata about the crawling process."""
    return {
        "symbol": symbol,
        "source_urls": source_urls,
        "crawler_used": crawler_used,
        "links_found": links_found,
        "downloaded_files": downloaded_files,
        "timestamp": datetime.now(UTC).isoformat(),
        "status": "completed"
    }

async def _throttle_by_domain(url: str, symbol: str) -> None:
    """Apply domain-specific rate limiting."""
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.lower()
    
    # Get or create lock for this domain
    if domain not in _domain_locks:
        _domain_locks[domain] = asyncio.Lock()
    
    # Get or create last accessed timestamp for this domain
    if domain not in _last_accessed:
        _last_accessed[domain] = 0
    
    # Acquire domain lock
    async with _domain_locks[domain]:
        # Calculate how long we need to wait
        last_access = _last_accessed[domain]
        rate_limit = DOMAIN_RATE_LIMITS.get(domain, 1.0)
        elapsed = time.time() - last_access
        wait_time = max(0, rate_limit - elapsed)
        
        if wait_time > 0:
            logger.debug(f"[DocumentCrawler] [{symbol}] throttling {domain} for {wait_time:.2f}s")
            await asyncio.sleep(wait_time)
        
        # Update last accessed timestamp
        _last_accessed[domain] = time.time()

async def process_single_company(symbol: str, urls: List[str], overwrite: bool = False) -> dict:
    """Process a single company asynchronously with domain throttling."""
    manifest_path = RAW_DOCUMENTS / symbol / "manifest.json"

    if not overwrite and manifest_path.exists():
        logger.info(f"[DocumentCrawler] [{symbol}] skipping — manifest exists")
        return {"status": "skipped"}

    (RAW_DOCUMENTS / symbol).mkdir(parents=True, exist_ok=True)
    (RAW_DOCUMENTS_OTHER / symbol).mkdir(parents=True, exist_ok=True)

    all_downloaded = []  # list of dicts from download_file()

    # Configure browser with memory optimizations
    browser_config = BrowserConfig(
        headless=True,
        text_mode=True,  # This automatically disables image loading and heavy asset rendering
        extra_args=["--disable-gpu", "--disable-extensions", "--disable-dev-shm-usage", "--no-sandbox"]
    )
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        page_timeout=30000,
        delay_before_return_html=2.0,
        exclude_external_links=True,
        word_count_threshold=10
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in urls:
            logger.info(f"[DocumentCrawler] [{symbol}] fetching seed URL: {url}")

            # Apply domain throttling before crawling
            await _throttle_by_domain(url, symbol)
            
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
                # Apply domain throttling before downloading
                href = urljoin(url, href)
                await _throttle_by_domain(href, symbol)
                
                doc_type, dest_dir = determine_download_destination(href, symbol)
                if doc_type == "skip":
                    continue

                filename = sanitize_filename(href)
                dest_path = dest_dir / filename

                if dest_path.exists() and not overwrite:
                    logger.debug(f"[DocumentCrawler] [{symbol}] already exists, skipping: {filename}")
                    continue

                success, error, final_path = await download_file(href, dest_path, symbol)
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

async def process_batch_companies(symbols: List[str], overwrite: bool = False) -> Dict[str, Any]:
    """Process multiple companies concurrently with semaphore control."""
    # Create semaphore to limit concurrent tasks (10-12 is optimal for 16GB M5)
    semaphore = asyncio.Semaphore(12)
    
    async def process_with_semaphore(symbol: str) -> Dict[str, Any]:
        async with semaphore:
            return await process_single_company(symbol, [], overwrite)
    
    # Create tasks for all symbols
    tasks = [process_with_semaphore(symbol) for symbol in symbols]
    
    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results and handle any exceptions
    processed_results = {}
    for symbol, result in zip(symbols, results):
        if isinstance(result, Exception):
            logger.error(f"[DocumentCrawler] [{symbol}] failed with exception: {result}")
            processed_results[symbol] = {"status": "failed", "error": str(result)}
        else:
            processed_results[symbol] = result
    
    return processed_results

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

def run_batch(symbols: List[str], overwrite: bool = False) -> Dict[str, Any]:
    """Run batch processing for multiple symbols."""
    return asyncio.run(process_batch_companies(symbols, overwrite))

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
        
    # Process all symbols concurrently
    symbols_list = list(company_urls.keys())
    logger.info(f"Starting batch processing for {len(symbols_list)} symbols")
    
    results = run_batch(symbols_list, overwrite=args.overwrite)
    
    # Log results
    succeeded = 0
    failed = 0
    skipped = 0
    
    for symbol, result in results.items():
        status = result.get("status", "unknown")
        if status == "success":
            succeeded += 1
        elif status == "failed":
            failed += 1
        elif status == "skipped":
            skipped += 1
    
    logger.info(f"Batch processing complete: {succeeded} succeeded, {failed} failed, {skipped} skipped")

if __name__ == "__main__":
    main()
    main()