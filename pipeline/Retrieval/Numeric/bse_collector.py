"""BSE (Bombay Stock Exchange) collector for Indian equity market data."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import pandas as pd

from pipeline.Retrieval.Numeric.base_numeric_collector import BaseNumericCollector


class BSECollector(BaseNumericCollector):
    """BSE collector for Indian stock data."""
    
    SOURCE_NAME = "bse"
    BASE_URL = "https://api.bseindia.com/BseIndiaAPI/api"
    BATCH_SIZE = 50
    MAX_RETRIES = 3
    OUTPUT_COLUMNS = [
        "symbol",
        "company_name", 
        "exchange",
        "sector",
        "market_cap",
        "price_change",
        "price_change_percent",
        "volume",
        "open_price",
        "high_price",
        "low_price",
        "close_price",
        "timestamp"
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.session = requests.Session()
        # Set necessary headers to avoid 403 errors
        self.session.headers.update({
            'Referer': 'https://www.bseindia.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def build_request(self, batch: list[str]) -> dict[str, Any]:
        """Build BSE request for a batch of symbols."""
        return {"symbols": batch}

    def fetch_batch(self, request: dict[str, Any]) -> Any:
        """Fetch data for a batch of symbols using BSE API with two-step pattern."""
        symbols = request["symbols"]
        data = {}
        failed_symbols = []
        
        # Fetching stock data from BSE using the two-step approach
        for symbol in symbols:
            try:
                # Step 1: Get company information to get bse_code
                company_info_url = f"{self.BASE_URL}/CompanyHeader/w"
                params = {
                    "quotetype": "EQ",
                    "scripcode": symbol  # Using symbol directly as scripcode for now
                }
                
                self.logger.debug(f"Fetching company info for {symbol}")
                response1 = self.session.get(company_info_url, params=params, timeout=10)
                response1.raise_for_status()
                
                # For demonstration, we'll parse what would be a JSON response from BSE API
                company_data = response1.json() if response1.content else {}
                
                # Step 2: Get price history using the bse_code or symbol
                price_history_url = f"{self.BASE_URL}/SMSpreader/w"
                params = {
                    "scripcode": symbol,  # Using symbol as scripcode for now  
                    "flag": 0
                }
                
                self.logger.debug(f"Fetching price history for {symbol}")
                response2 = self.session.get(price_history_url, params=params, timeout=10)
                response2.raise_for_status()
                
                # Parse the price history data
                price_data = response2.json() if response2.content else {}
                
                # Combine both sets of data
                combined_data = {
                    "company_info": company_data,
                    "price_history": price_data,
                    "bse_code": symbol  # This would normally be extracted from company_info
                }
                
                data[symbol] = combined_data
                
                # Enforce 2-second delay between requests as required
                import time
                time.sleep(2)
                
            except Exception as e:
                self.logger.warning(f"Failed to fetch data for {symbol}: {e}")
                failed_symbols.append(symbol)
        
        return {"data": data, "failed_symbols": failed_symbols}

    def parse_response(self, response: Any) -> list[dict]:
        """Parse BSE response into records."""
        records = []
        data = response.get("data", {})
        
        for symbol, info in data.items():
            try:
                # Extract relevant information from the BSE API response structure
                company_info = info.get('company_info', {})
                price_info = info.get('price_history', {})
                
                # Structure according to schema - this will depend on actual BSE API response format
                record = {
                    "symbol": symbol.upper(),
                    "company_name": company_info.get('CompanyName', '').strip(),
                    "exchange": "BSE",  # Always BSE for this collector
                    "sector": company_info.get('Sector', ''),  # This may need to be extracted differently
                    "market_cap": company_info.get('MarketCap', 0),
                    "price_change": price_info.get('Change', 0),
                    "price_change_percent": price_info.get('ChangePercent', 0.0),
                    "volume": price_info.get('Volume', 0),
                    "open_price": price_info.get('Open', 0),
                    "high_price": price_info.get('High', 0), 
                    "low_price": price_info.get('Low', 0),
                    "close_price": price_info.get('Close', 0),
                    "timestamp": datetime.utcnow().isoformat() + "+00:00"
                }
                records.append(record)
            except Exception as e:
                self.logger.error(f"Error parsing data for {symbol}: {e}")
                
        return records

    def normalize_record(self, record: dict) -> dict:
        """Normalize a single record."""
        # Ensure all required fields exist
        normalized = {}
        for column in self.OUTPUT_COLUMNS:
            normalized[column] = record.get(column, None)
        return normalized