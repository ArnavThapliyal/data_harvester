"""
Yahoo Finance collector for financial data.
"""

import json
import logging
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd
import yfinance as yf

from Retrieval.Numeric.base_numeric_collector import BaseNumericCollector

logger = logging.getLogger(__name__)


class YFinanceCollector(BaseNumericCollector):
    SOURCE_NAME = "yfinance"
    BASE_URL = "https://finance.yahoo.com/quote/"
    BATCH_SIZE = 50
    MAX_RETRIES = 3
    OUTPUT_COLUMNS = [
        "symbol",
        "company_name",
        "exchange",
        "isin",
        "sector",
        "industry",
        "market_cap",
        "pe_ratio",
        "price_earnings_growth",
        "dividend_yield",
        "beta",
        "52_week_high",
        "52_week_low",
        "volume",
        "avg_volume_3_month",
        "open_price",
        "close_price",
        "high_price",
        "low_price",
        "timestamp",
    ]

    def build_request(self, batch: list[str]) -> dict:
        """Build batch request with symbols."""
        return {"symbols": batch}

    def fetch_batch(self, request: dict) -> dict:
        """Fetch data for multiple symbols from Yahoo Finance."""
        symbols = request["symbols"]
        results = {}
        
        for symbol in symbols:
            try:
                # Add delay between requests to avoid rate limiting
                time.sleep(2)
                
                # Create yfinance ticker object with proper suffix for Indian stocks
                ticker_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
                
                # Get ticker data
                ticker = yf.Ticker(ticker_symbol)
                
                # Fetch OHLCV data
                history = ticker.history(period="max")
                history_dict = history.to_dict(orient="records") if not history.empty else []
                
                # Get fundamental info
                info = ticker.info or {}
                
                # Get financials data (income statement)
                financials = ticker.financials
                financials_dict = financials.to_dict(orient="records") if not financials.empty else []
                
                results[symbol] = {
                    "symbol": symbol,
                    "history": history_dict,
                    "info": info,
                    "financials": financials_dict,
                }
            except Exception as e:
                logger.warning(f"Failed to fetch data for {symbol}: {e}")
                results[symbol] = {"error": str(e)}
                
        return results

    def parse_response(self, response: dict) -> list[dict]:
        """Parse the Yahoo Finance response into records."""
        records = []
        
        for symbol, data in response.items():
            if "error" in data:
                continue
                
            # Extract basic info from ticker.info
            info = data.get("info", {})
            
            # Create record with combined data
            record = {
                "symbol": symbol,
                "company_name": info.get("longName", ""),
                "exchange": "NSE",
                "isin": info.get("isin", ""),
                "sector": info.get("sector", ""),
                "industry": info.get("industry", ""),
                "market_cap": info.get("marketCap", None),
                "pe_ratio": info.get("trailingPE", None),
                "price_earnings_growth": info.get("pegRatio", None),
                "dividend_yield": info.get("dividendYield", None),
                "beta": info.get("beta", None),
                "52_week_high": info.get("week52High", None),
                "52_week_low": info.get("week52Low", None),
                "volume": info.get("volume", None),
                "avg_volume_3_month": info.get("averageVolume3Month", None),
                "open_price": info.get("open", None),
                "close_price": info.get("previousClose", None),
                "high_price": info.get("dayHigh", None),
                "low_price": info.get("dayLow", None),
                "timestamp": datetime.now(UTC).isoformat(),
            }
            
            records.append(record)
            
        return records

    def normalize_record(self, record: dict) -> dict:
        """Normalize a single record to the expected format."""
        # All fields already match the OUTPUT_COLUMNS
        return record