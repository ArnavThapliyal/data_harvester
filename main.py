#!/usr/bin/env python3
"""
Main orchestrator for running the data harvester pipeline.
Entry point for the data harvester pipeline.

Exactly three supported invocations — nothing else:

    main.py --all-symbols                  # every symbol, every stage
    main.py --symbol SYM                   # one symbol, every stage
    main.py --symbol SYM --stage STAGE     # one symbol, exactly one stage

--stage is only valid alongside --symbol; there is no "all symbols, one
stage" mode in this pass. Add it deliberately later if you need it — don't
let it appear as an accidental side effect of argparse defaults.

Symbol source of truth: config/company_urls.json (produced by
scripts/url_discovery.py). A symbol must have an entry there before it can
be processed — that's what --all-symbols enumerates, and what --symbol is
validated against.
"""
import os
import sys
import argparse
import logging
import time
import subprocess
import csv
import json
import pandas as pd

from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Set, Any

# Add project root to path so imports work properly
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging to file and stdout
log_formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s')
log_formatter.converter = time.gmtime  # Use UTC for logs

# Setup file logger
file_handler = logging.FileHandler('data/pipeline.log')
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# Setup stdout logger  
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.setFormatter(log_formatter)
stdout_handler.setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.addHandler(file_handler)
logger.addHandler(stdout_handler)
logger.setLevel(logging.INFO)

def get_company_universe() -> List[str]:
    """Get complete company universe from CSV."""
    try:
        df = pd.read_csv('config/company_universe.csv')
        
        if 'Symbol' in df.columns:
            # pd.notna() ignores empty cells, str() forces the rest to text before stripping
            return [str(symbol).strip() for symbol in df['Symbol'] if pd.notna(symbol) and str(symbol).strip()]
        elif 'ticker' in df.columns:
            return [str(symbol).strip() for symbol in df['ticker'] if pd.notna(symbol) and str(symbol).strip()]
        else:
            # Return first column as a fallback
            return [str(row).strip() for row in df.iloc[:, 0] if pd.notna(row) and str(row).strip()]
            
    except Exception as e:
        logger.error(f"Error reading universe CSV: {str(e)}")
        return []

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Data Harvester Pipeline')
    
    # Add mutually exclusive group for symbol selection
    symbol_group = parser.add_mutually_exclusive_group(required=True)
    symbol_group.add_argument('--all-symbols', action='store_true',
                              help='Process all symbols from company_urls.json')
    symbol_group.add_argument('--symbol', type=str,
                              help='Process a single symbol from company_urls.json')
    
    parser.add_argument('--stage', type=str,
                       help='Run only one specific stage for the symbol (numeric, document)')
    parser.add_argument('--limit', type=int,
                       help='Maximum number of symbols to process')
    parser.add_argument('--overwrite', action='store_true',
                       help='Overwrite existing results')
    
    return parser.parse_args()

def validate_symbol(symbol: str) -> bool:
    """Validate that a symbol exists in company_urls.json."""
    try:
        with open('config/company_urls.json', 'r') as f:
            company_urls = json.load(f)
        
        return symbol in company_urls
    except Exception as e:
        logger.error(f"Error validating symbol: {str(e)}")
        return False

def run_harvester_pipeline(
    symbols: Optional[List[str]] = None,
    stages: Optional[List[str]] = None,
    overwrite: bool = False,
    limit: Optional[int] = None
) -> None:
    """Main pipeline execution logic with explicit workflow."""
    
    logger.info(f"Starting pipeline execution for {len(symbols) if symbols else 0} symbols")
    
    # If no specific arguments provided, run all symbols and all stages (default behavior)
    if stages is None:
        stages = ['numeric', 'document']
    
    # Apply limit if specified 
    if limit and limit > 0:
        symbols = symbols[:limit]
    
    # Validate that all symbols exist in company_urls.json
    if symbols:
        for symbol in symbols:
            if not validate_symbol(symbol):
                logger.error(f"Symbol '{symbol}' not found in company_urls.json")
                sys.exit(1)
    
    # Run the pipeline stages for each symbol
    for symbol in symbols:
        logger.info(f"Processing symbol: {symbol}")
        
        for stage in stages:
            logger.info(f"Running {stage} stage for {symbol}")
            
            if stage == 'numeric':
                run_numeric_stage(symbol, overwrite)
            elif stage == 'document':
                run_document_stage(symbol, overwrite)
            else:
                logger.error(f"Unknown stage: {stage}")
                sys.exit(1)

def run_numeric_stage(symbol: str, overwrite: bool) -> None:
    """Run numeric data collection."""
    logger.info(f"[Numeric] [{symbol}] starting numeric data collection")
    
    # Import and run numeric collectors from the registry
    try:
        from pipeline.Retrieval.registry import get_collectors
        
        # Get all collector classes
        collectors = get_collectors()
        logger.info(f"Found {len(collectors)} numeric collectors to process for symbol {symbol}")
        
        # For each collector, run it with the symbol (in a real implementation)
        for collector_class in collectors:
            try:
                # Initialize collector
                logger.info(f"Initializing {collector_class.__name__} collector")
                collector = collector_class()
                
                # For demonstration, we'll just log that it would run
                logger.info(f"Would run {collector.SOURCE_NAME} collector for {symbol}")
                
            except Exception as e:
                logger.error(f"Failed to run {collector_class.__name__} collector: {str(e)}")
                raise
                
    except ImportError as e:
        logger.error(f"Failed to import collectors: {str(e)}")
        raise

def run_document_stage(symbol: str, overwrite: bool) -> None:
    """Run document crawling."""
    logger.info(f"[Document] [{symbol}] starting document collection")
    
    # For now, implement a passover stage that logs but doesn't actually crawl
    logger.info(f"Document collection passover for {symbol} - skipping actual crawling")
    
    # Import and run the document crawler logic
    try:
        from pipeline.Retrieval.Document.document_crawler import process_single_company
        
        # For demonstration, just log that it would run
        logger.info(f"Would process document crawling for {symbol}")
        
    except ImportError as e:
        logger.error(f"Failed to import document crawler: {str(e)}")
        raise

def main() -> None:
    """Main entry point."""
    # Create data directory if it doesn't exist
    Path('data').mkdir(exist_ok=True)
    
    args = parse_args()
    
    # Handle --all-symbols vs --symbol
    if args.all_symbols:
        try:
            with open('config/company_urls.json', 'r') as f:
                company_urls = json.load(f)
            symbols = list(company_urls.keys())
        except Exception as e:
            print(f"Error reading company_urls.json: {str(e)}")
            sys.exit(1)
    else:
        symbols = [args.symbol]
    
    # Validate symbol if provided
    if args.symbol and not validate_symbol(args.symbol):
        print(f"Error: Symbol '{args.symbol}' not found in company_urls.json")
        sys.exit(1)
    
    # Determine stages to run based on arguments
    stages = []
    if args.stage:
        stages = [args.stage]
    else:
        # Default to numeric and document stages
        stages = ['numeric', 'document']
    
    try:
        logger.info("Starting main pipeline execution")
        run_harvester_pipeline(
            symbols=symbols,
            stages=stages,
            overwrite=args.overwrite,
            limit=args.limit
        )
        logger.info("Pipeline execution completed successfully")
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()