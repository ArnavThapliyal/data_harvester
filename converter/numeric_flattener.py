"""
Numeric flattener for standardizing raw collector data to unified schema.
"""
from pathlib import Path
import json
import tempfile
import shutil


def flatten(src: Path, dest: Path) -> dict:
    """
    Read a raw numeric collector JSON from data/raw/ and write a normalized version to data/trans/numeric/.
    
    Args:
        src: Path to source raw JSON file
        dest: Path to destination flattened JSON file
        
    Returns:
        dict with symbol, source, rows, success, error keys
    """
    result = {
        "symbol": None,
        "source": None,
        "rows": 0,
        "success": False,
        "error": None
    }
    
    try:
        # Read the raw data
        with open(src, 'r') as f:
            raw_data = json.load(f)
        
        # Extract symbol and source from file name or raw data
        symbol = src.stem
        result["symbol"] = symbol
        
        # Determine source from file path or raw data
        source = None
        if "indiaapi" in str(src).lower():
            source = "IndiaAPI"
        elif "yfinance" in str(src).lower():
            source = "YFinance"
        elif "nse" in str(src).lower():
            source = "NSE"
        elif "bsc" in str(src).lower():
            source = "BSE"
        else:
            # Try to extract from raw data if not from path
            if isinstance(raw_data, dict) and 'endpoint' in raw_data:
                if 'historical_data' in raw_data['endpoint']:
                    source = "IndiaAPI"
                else:
                    source = "Unknown"
            else:
                source = "Unknown"
        
        result["source"] = source
        
        # Normalize the data based on source
        normalized_data = {
            "symbol": symbol,
            "source": source,
            "fetched_at": None,
            "ohlcv": [],
            "fundamentals": {
                "pe_ratio": None,
                "pb_ratio": None,
                "market_cap": None,
                "dividend_yield": None,
                "52w_high": None,
                "52w_low": None
            }
        }
        
        # Process based on source type
        if source == "IndiaAPI":
            normalized_data["fetched_at"] = raw_data.get("fetched_at")
            
            # Handle India API specific data structure
            if "data" in raw_data and isinstance(raw_data["data"], dict):
                data = raw_data["data"]
                # Process OHLCV data from IndiaAPI
                if "historical_prices" in data and isinstance(data["historical_prices"], list):
                    ohlcv_list = []
                    for price_entry in data["historical_prices"]:
                        ohlcv_item = {
                            "date": price_entry.get("date"),
                            "open": price_entry.get("open_price", price_entry.get("open")),
                            "high": price_entry.get("high_price", price_entry.get("high")),
                            "low": price_entry.get("low_price", price_entry.get("low")),
                            "close": price_entry.get("close_price", price_entry.get("close")),
                            "volume": price_entry.get("volume")
                        }
                        ohlcv_list.append(ohlcv_item)
                    normalized_data["ohlcv"] = ohlcv_list
                    result["rows"] = len(ohlcv_list)
                
                # Extract fundamentals from IndiaAPI data
                if "fundamentals" in data and isinstance(data["fundamentals"], dict):
                    fundamental_data = data["fundamentals"]
                    normalized_data["fundamentals"]["pe_ratio"] = fundamental_data.get("pe_ratio", fundamental_data.get("pe"))
                    normalized_data["fundamentals"]["pb_ratio"] = fundamental_data.get("pb_ratio", fundamental_data.get("pb"))
                    normalized_data["fundamentals"]["market_cap"] = fundamental_data.get("market_cap")
                    normalized_data["fundamentals"]["dividend_yield"] = fundamental_data.get("dividend_yield")
                    normalized_data["fundamentals"]["52w_high"] = fundamental_data.get("52w_high")
                    normalized_data["fundamentals"]["52w_low"] = fundamental_data.get("52w_low")
        
        elif source == "YFinance":
            # Handle YFinance data structure
            normalized_data["fetched_at"] = raw_data.get("fetched_at") if isinstance(raw_data, dict) else None
            
            # Extract OHLCV from YFinance data (typically stored in a 'data' or similar field)
            if isinstance(raw_data, dict):
                # Try to find OHLC data
                history = raw_data.get('history')
                if isinstance(history, list):
                    ohlcv_list = []
                    for item in history:
                        if isinstance(item, dict):
                            ohlcv_item = {
                                "date": item.get("Date"),
                                "open": item.get("Open"),
                                "high": item.get("High"),
                                "low": item.get("Low"),
                                "close": item.get("Close"),
                                "volume": item.get("Volume")
                            }
                            ohlcv_list.append(ohlcv_item)
                    normalized_data["ohlcv"] = ohlcv_list
                    result["rows"] = len(ohlcv_list)
                else:
                    # Try other possible structures
                    for key, value in raw_data.items():
                        if isinstance(value, list) and len(value) > 0:
                            if "open" in str(value[0]).lower() or "close" in str(value[0]).lower():
                                ohlcv_list = []
                                for item in value:
                                    if isinstance(item, dict):
                                        ohlcv_item = {
                                            "date": item.get("date", item.get("Date")),
                                            "open": item.get("open", item.get("Open")),
                                            "high": item.get("high", item.get("High")),
                                            "low": item.get("low", item.get("Low")),
                                            "close": item.get("close", item.get("Close")),
                                            "volume": item.get("volume", item.get("Volume"))
                                        }
                                        ohlcv_list.append(ohlcv_item)
                                normalized_data["ohlcv"] = ohlcv_list
                                result["rows"] = len(ohlcv_list)
                                break
                
                # Extract fundamentals from YFinance data
                fundamentals = raw_data.get('fundamentals', {})
                if isinstance(fundamentals, dict):
                    normalized_data["fundamentals"]["pe_ratio"] = fundamentals.get("pe_ratio", fundamentals.get("pe"))
                    normalized_data["fundamentals"]["pb_ratio"] = fundamentals.get("pb_ratio", fundamentals.get("pb"))
                    normalized_data["fundamentals"]["market_cap"] = fundamentals.get("market_cap")
                    normalized_data["fundamentals"]["dividend_yield"] = fundamentals.get("dividend_yield")
                    normalized_data["fundamentals"]["52w_high"] = fundamentals.get("52w_high")
                    normalized_data["fundamentals"]["52w_low"] = fundamentals.get("52w_low")
        
        elif source in ["NSE", "BSE"]:
            # For NSE/BSE collectors
            normalized_data["fetched_at"] = raw_data.get("fetched_at")
            
            if isinstance(raw_data, dict):
                data = raw_data.get('data', {})
                
                # Extract OHLCV
                if 'historical' in data and isinstance(data['historical'], list):
                    ohlcv_list = []
                    for price_entry in data['historical']:
                        if isinstance(price_entry, dict) and "date" in price_entry:
                            ohlcv_item = {
                                "date": price_entry.get("date"),
                                "open": price_entry.get("open_price", price_entry.get("open")),
                                "high": price_entry.get("high_price", price_entry.get("high")),
                                "low": price_entry.get("low_price", price_entry.get("low")),
                                "close": price_entry.get("close_price", price_entry.get("close")),
                                "volume": price_entry.get("volume")
                            }
                            ohlcv_list.append(ohlcv_item)
                    normalized_data["ohlcv"] = ohlcv_list
                    result["rows"] = len(ohlcv_list)
                
                # Extract fundamentals
                if 'fundamentals' in data and isinstance(data['fundamentals'], dict):
                    fundamental_data = data['fundamentals']
                    normalized_data["fundamentals"]["pe_ratio"] = fundamental_data.get("pe_ratio", fundamental_data.get("pe"))
                    normalized_data["fundamentals"]["pb_ratio"] = fundamental_data.get("pb_ratio", fundamental_data.get("pb"))
                    normalized_data["fundamentals"]["market_cap"] = fundamental_data.get("market_cap")
                    normalized_data["fundamentals"]["dividend_yield"] = fundamental_data.get("dividend_yield")
                    normalized_data["fundamentals"]["52w_high"] = fundamental_data.get("52w_high")
                    normalized_data["fundamentals"]["52w_low"] = fundamental_data.get("52w_low")
        
        # Write to temporary file first, then rename atomically
        temp_file = dest.with_suffix(dest.suffix + '.tmp')
        with open(temp_file, 'w') as f:
            json.dump(normalized_data, f, indent=2)
            
        # Atomically move temp file to destination
        shutil.move(temp_file, dest)
        result["success"] = True
        
    except Exception as e:
        result["error"] = str(e)
        result["success"] = False
            
    return result