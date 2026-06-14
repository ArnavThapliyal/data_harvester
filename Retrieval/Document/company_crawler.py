"""Web crawler for company documents and investor relations data."""
import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests
from bs4 import BeautifulSoup
from crawl4ai import Crawl4AI
from crawl4ai.web_crawler import WebCrawler

from config.settings import RAW_DOCUMENTS_OTHER


class CompanyCrawler:
    """Web crawler for company documents and investor relations data."""
    
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
        """Find the investor relations website for a company."""
        try:
            # This would be a more sophisticated search in reality
            # For now we'll just use a basic approach
            search_query = f"{company_name} investor relations site"
            
            # Using Google search as example (would need to implement proper API)
            self.logger.debug(f"Searching for IR site: {search_query}")
            
            # Simulate finding an IR site
            ir_site = None
            
            # This is a simplified approach - in practice you'd use 
            # actual search APIs or more sophisticated techniques
            if company_name.lower() == "reliance":
                ir_site = "https://www.reliance.com/investor-relations"
            elif company_name.lower() == "tata motors":
                ir_site = "https://www.tatamotors.com/investor-relations"
                
            return ir_site
            
        except Exception as e:
            self.logger.error(f"Error finding IR site for {company_name}: {e}")
            return None
    
    def crawl_site(self, url: str) -> Optional[Dict[str, Any]]:
        """Crawl a website and extract relevant information."""
        try:
            # Using Crawl4AI to crawl the site
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
                response = requests.get(url, timeout=30)
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
        companies = self.load_company_list()
        
        for company in companies[:5]:  # Limit for demonstration
            self.logger.info(f"Crawling data for {company['company_name']} ({company['symbol']})")
            
            # Find IR site
            ir_site = self.find_ir_site(company['company_name'])
            if not ir_site:
                self.logger.warning(f"No IR site found for {company['company_name']}")
                continue
            
            # Crawl the site
            crawl_result = self.crawl_site(ir_site)
            if not crawl_result:
                continue
                
            # Extract document links
            doc_links = self.extract_document_links(crawl_result['content'], ir_site)
            
            # Download documents
            downloaded_docs = self.download_documents(doc_links[:3])  # Limit to 3 docs
            
            # Save metadata
            company_crawl_data = {
                'company_name': company['company_name'],
                'symbol': company['symbol'],
                'exchange': company['exchange'],
                'ir_site': ir_site,
                'crawl_time': crawl_result['crawl_time'],
                'documents_downloaded': len(downloaded_docs),
                'downloaded_docs': downloaded_docs
            }
            
            self.save_metadata(company_crawl_data)
            
            # Add delay to be respectful to servers
            time.sleep(1)

    def process_single_company(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Process a single company by symbol."""
        companies = self.load_company_list()
        company = next((c for c in companies if c['symbol'].lower() == symbol.lower()), None)
        
        if not company:
            self.logger.error(f"Company with symbol {symbol} not found")
            return None
            
        ir_site = self.find_ir_site(company['company_name'])
        if not ir_site:
            self.logger.warning(f"No IR site found for {company['company_name']}")
            return None
            
        crawl_result = self.crawl_site(ir_site)
        if not crawl_result:
            return None
            
        doc_links = self.extract_document_links(crawl_result['content'], ir_site)
        downloaded_docs = self.download_documents(doc_links[:3])
        
        company_crawl_data = {
            'company_name': company['company_name'],
            'symbol': company['symbol'],
            'exchange': company['exchange'],
            'ir_site': ir_site,
            'crawl_time': crawl_result['crawl_time'],
            'documents_downloaded': len(downloaded_docs),
            'downloaded_docs': downloaded_docs
        }
        
        self.save_metadata(company_crawl_data)
        
        return company_crawl_data