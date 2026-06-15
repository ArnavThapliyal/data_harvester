"""
Unified document crawler for downloading files from company URLs using fallback approach.
This implementation combines the best practices from company_crawler and document_crawler.
"""

import argparse
import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import List, Optional, Dict, Any 
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup
from crawl4ai import Crawl4AI
from crawl4ai.web_crawler import WebCrawler

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


def sanitize_filename(url: str, max_length: int = 200) -> str:
    """Sanitize a URL into a safe filename."""
    # Extract filename from URL
    parsed = urlparse(url)
    filename = Path(parsed.path).name or f"file_{int(time.time())}"
    
    # Remove unsafe characters - only allow alphanumeric, underscores, dots, hyphens  
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-")
    cleaned = ''.join(char for char in filename if char in safe_chars)
    
    if not cleaned or not any(c.isalnum() for c in cleaned):
        # Fallback to timestamp if nothing is safe
        cleaned = f"file_{int(time.time())}"
        
    # Truncate if too long
    cleaned = cleaned[:max_length]
    
    return cleaned


def get_file_extension(url: str) -> str:
    """Get file extension from URL.""" 
    parsed = urlparse(url)
    path = parsed.path
    
    # Extract extension from path first
    if path:
        ext = os.path.splitext(path)[1].lower()
        if ext:
            return ext
            
    # For cases with no extension in path, look at query parameters
    if parsed.query:
        for param in parsed.query.split('&'):
            if '=' in param:
                key, value = param.split('=', 1)
                if key.lower() in ('filename', 'file') and '.' in value:
                    ext = os.path.splitext(value)[1].lower()
                    if ext:
                        return ext
    
    # Default to .html if no extension found
    return ".html"


def determine_download_destination(url: str, symbol: str) -> tuple[str, Path]:
    """Determine which directory to download a file to based on its extension."""
    ext = get_file_extension(url)
    
    if ext in PROCESSABLE_EXTENSIONS:
        # Files for pipeline processing go to the symbol's main documents directory
        return "pipeline", RAW_DOCUMENTS / symbol
    elif ext in OTHER_EXTENSIONS:
        # Files that don't get processed further go to other directory
        return "other", RAW_DOCUMENTS_OTHER / symbol
    else:
        # Unknown extensions are not downloaded
        return "unknown", Path()  # Return empty path


def is_url_downloadable(url: str, timeout: int = 5) -> tuple[bool, Optional[str]]:
    """Check if URL points to a downloadable file by examining HTTP headers."""
    try:
        response = httpx.head(url, timeout=timeout)
        
        content_type = response.headers.get('content-type', '')
        
        # If we already have a specific extension, validate it's likely to be a document
        ext = get_file_extension(url).lower()
        if ext in PROCESSABLE_EXTENSIONS or ext in OTHER_EXTENSIONS:
            return True, content_type
            
        # For unknown extensions, check if it looks like a downloadable binary file
        if any(ct in content_type.lower() for ct in ['application/', 'binary', 'octet-stream']):
            return True, content_type
        
        return False, content_type
    except Exception:
        return False, None


def extract_links_with_beautifulsoup(content: str, base_url: str) -> List[str]:
    """Extract links using BeautifulSoup."""
    soup = BeautifulSoup(content, 'html.parser')
    links = []
    
    # Look for common anchor tags with href attributes  
    for link in soup.find_all('a', href=True):
        href = link['href']
        
        # Skip if it's a javascript or email link
        if href.startswith(('javascript:', 'mailto:')):
            continue
            
        # Convert relative URLs to absolute URLs if needed
        absolute_url = href
        if not href.startswith(('http://', 'https://')):
            try:
                parsed_base = urlparse(base_url)
                resolved_path = os.path.join(parsed_base.path, href) 
                absolute_url = f"{parsed_base.scheme}://{parsed_base.netloc}{resolved_path}"
            except Exception:
                continue
                
        links.append(absolute_url)
        
    return links


def download_file(url: str, destination: Path, symbol: str) -> tuple[bool, Optional[str], Optional[int]]:
    """Download a single file with error handling."""
    try:
        # Ensure destination directory exists
        destination.parent.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Downloading {url} to {destination}")
        
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        
        # Write file in chunks to avoid memory issues
        with open(destination, 'wb') as f:
            for chunk in response.iter_bytes(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        return True, None, len(response.content)
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Failed to download {url} for {symbol}: {error_msg}")
        return False, error_msg, None


def create_manifest(symbol: str, source_urls: List[str], crawler_used: str, links_found: int, files_downloaded: List[dict]) -> dict:
    """Create manifest file for a symbol's document collection."""
    # Use the first URL as the main source for this manifest
    main_source = source_urls[0] if source_urls else ""
    
    manifest = {
        "symbol": symbol,
        "last_run": datetime.now(UTC).isoformat(),
        "total_files": len(files_downloaded),
        "sources": [
            {
                "source_url": main_source,
                "crawled_at": datetime.now(UTC).isoformat(),
                "crawler_used": crawler_used,
                "links_found": links_found,
                "files_downloaded": files_downloaded
            }
        ]
    }
    return manifest


def process_single_company(symbol: str, urls: List[str], overwrite: bool = False) -> None:
    """Process all URLs for a single symbol."""
    logger.info(f"Processing {len(urls)} URLs for symbol {symbol}")
    
    # Create directories for this symbol
    symbol_outputs_dir = RAW_DOCUMENTS / symbol
    symbol_other_dir = RAW_DOCUMENTS_OTHER / symbol
    
    # Create manifest file path (check if we should skip due to existing manifest)
    manifest_path = symbol_outputs_dir / "manifest.json"
    
    # Check if we should resume (skip if manifest exists and overwrite is false)
    if not overwrite and manifest_path.exists():
        try:
            with open(manifest_path, 'r') as f:
                existing_manifest = json.load(f)
                logger.info(f"Skipping {symbol} - manifest already exists")
                return
        except Exception:
            pass  # If we can't load existing manifest, proceed to overwrite
    
    # List of files we successfully download
    all_downloaded_files = []
    
    # For each URL, try to extract links and download files
    for i, url in enumerate(urls):
        logger.debug(f"Processing URL {i+1}/{len(urls)}: {url}")
        
        # Use HTTP approach as fallback method (since crawl4ai is not available)
        crawler_used = "httpx"
        links = []
        
        try:
            response = httpx.get(url, timeout=10)
            if response.status_code == 200:
                links = extract_links_with_beautifulsoup(response.text, url)
                logger.info(f"Found {len(links)} links from {url}")
            else:
                logger.warning(f"HTTP request failed with status {response.status_code} for {url}")
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            continue
        
        # Also include the base URL itself if it's a file download
        ext = get_file_extension(url).lower()
        if (ext in PROCESSABLE_EXTENSIONS or ext in OTHER_EXTENSIONS) and url not in links:
            links.append(url)  # Add the URL itself as a file to download
            
        for link in links:
            # Determine destination
            dest_type, dest_dir = determine_download_destination(link, symbol)
            
            if dest_type == "unknown":
                continue
                
            # Get filename from URL
            filename = sanitize_filename(link)
            ext = os.path.splitext(filename)[1].lower()
            
            # Add counter to avoid overwrites  
            counter = 1
            final_dest = dest_dir / filename
            
            while final_dest.exists() and not overwrite:
                name, ext = os.path.splitext(filename)
                new_filename = f"{name}_{counter}{ext}" 
                final_dest = dest_dir / new_filename
                counter += 1
                
            # Check if it's a downloadable file
            is_downloadable, content_type = is_url_downloadable(link, timeout=5) 
            
            if not is_downloadable:
                logger.debug(f"URL does not appear to be a direct download: {link}")
                continue
            
            # Download the file  
            success, error_msg, size_bytes = download_file(link, final_dest, symbol)
            
            all_downloaded_files.append({
                "url": link,
                "filename": final_dest.name,
                "size_bytes": size_bytes,
                "downloaded_at": datetime.now(UTC).isoformat(),
                "success": success,
                "error": error_msg
            })
        
        # Add a small delay between URLs to be respectful
        time.sleep(0.5)
    
    # Create and save manifest file (even if no files found)
    if all_downloaded_files:
        manifest = create_manifest(symbol, urls, crawler_used, len(links), all_downloaded_files)
        
        try:
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            logger.info(f"Saved manifest for {symbol}: {manifest_path}")
        except Exception as e:
            logger.error(f"Failed saving manifest for {symbol}: {e}")
    else:
        logger.warning(f"No files downloaded for symbol {symbol}")


class UnifiedDocumentCrawler:
    """Unified document crawler combining best features of both original crawler implementations."""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or RAW_DOCUMENTS_OTHER
        self.logger = logging.getLogger(self.__class__.__name__)
        self.crawler = Crawl4AI()
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
    def load_company_list(self) -> List[Dict[str, str]]:
        """Load the company universe list from CSV."""
        from config.settings import COMPANY_UNIVERSE_CSV
        
        companies = []
        try:
            import csv
            with COMPANY_UNIVERSE_CSV.open(newline='', encoding='utf-8') as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    if row.get('symbol'):  # Only include entries with symbols
                        companies.append({
                            'symbol': row['symbol'].strip(),
                            'company_name': row.get('company_name', '').strip(),
                            'exchange': row.get('exchange', '').strip()
                        })
        except Exception as e:
            self.logger.error(f"Failed to load company list: {e}")
            
        return companies
        
    def find_ir_site(self, company_name: str) -> Optional[str]:
        """Find the investor relations website for a company. Placeholder implementation."""
        # This would be enhanced in real implementation with proper search methods
        # For now returns None to trigger fallback
        self.logger.debug(f"Searching for IR site for {company_name}")
        return None  # Placeholder
        
    def crawl_site(self, url: str) -> Optional[Dict[str, Any]]:
        """Crawl a website and extract relevant information using Crawl4AI."""
        try:
            # Using Crawl4AI to crawl the site - this provides better content extraction
            result = self.crawler.web_crawler(
                url=url,
                word_count_threshold=100,
                extract_links=True,
                include_html=False,
                chunk_size=2000
            )
            
            if result.success:
                return {
                    'url': url,
                    'title': result.title,
                    'content': result.markdown,
                    'links': result.extracted_links,
                    'crawl_time': datetime.utcnow().isoformat() + "+00:00"
                }
            else:
                self.logger.warning(f"Crawl failed for {url}: {result.error}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error crawling site {url}: {e}")
            return None
            
    def extract_document_links(self, content: str, url: str) -> List[str]:
        """Extract document links from crawled content."""
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Find all links that point to documents
            doc_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if any(ext in href.lower() for ext in ['.pdf', '.doc', '.xls', '.xlsx', '.docx']):
                    # Convert relative URLs to absolute
                    if not href.startswith('http'):
                        from urllib.parse import urljoin
                        href = urljoin(url, href)
                    doc_links.append(href)
            
            return doc_links
            
        except Exception as e:
            self.logger.error(f"Error extracting document links: {e}")
            return []
            
    def download_documents(self, doc_urls: List[str]) -> List[Dict[str, Any]]:
        """Download and store documents."""
        downloaded = []
        
        for url in doc_urls:
            try:
                response = httpx.get(url, timeout=30)
                response.raise_for_status()
                
                # Create filename based on URL
                filename = os.path.basename(url)
                if not filename or '.' not in filename:
                    filename = f"document_{int(time.time())}.pdf"
                
                filepath = self.output_dir / f"{filename}"
                
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                downloaded.append({
                    'url': url,
                    'path': str(filepath),
                    'size': len(response.content),
                    'download_time': datetime.utcnow().isoformat() + "+00:00"
                })
                
            except Exception as e:
                self.logger.error(f"Error downloading {url}: {e}")
                continue
                
        return downloaded
        
    def save_metadata(self, company_data: Dict[str, Any]) -> None:
        """Save crawler metadata for the company."""
        try:
            # Create filename based on company name
            filename = f"{company_data['symbol']}_crawl_metadata.json"
            filepath = self.output_dir / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(company_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Error saving metadata: {e}")
            
    def crawl_companies(self) -> None:
        """Main method to crawl all companies in universe."""
        try:
            # Read company urls from file
            with open(COMPANY_URLS_JSON, 'r') as f:
                company_urls = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to read company URLs file: {e}")
            return
            
        # Process each symbol in the URL list
        symbols = list(company_urls.keys())
        for symbol in symbols[:5]:  # Limit for demo purposes
            urls = company_urls.get(symbol, [])
            if not urls:
                self.logger.warning(f"No URLs found for symbol {symbol}")
                continue
                
            self.logger.info(f"Crawling data for symbol: {symbol}")
            process_single_company(symbol, urls)
    
    def process_symbol_urls(self, symbol: str, urls: List[str], overwrite: bool = False):
        """Process individual symbol - wrapper around the standalone function."""
        process_single_company(symbol, urls, overwrite)


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