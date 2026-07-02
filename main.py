#!/usr/bin/env python3
"""
Main orchestrator for running the data harvester pipeline.
"""
import os
import sys
import argparse
import logging
import time
import subprocess
import csv
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Set

from scripts.url_discovery import generate_constant_urls, main as url_discovery_main
from scripts.build_universe import build_universe
from pipeline.pipeline import PipelineRunner
from config.settings import COMPANY_UNIVERSE_CSV, COMPANY_URLS_JSON, DONE

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


# def get_available_symbols() -> List[str]:
#     """Get list of available symbols from universe CSV."""
#     try:
#         import pandas as pd
#         universe_file = Path('config/company_universe.csv')
        
#         if not universe_file.exists():
#             logger.warning("Universe file not found, using default symbols")
#             return ['RELIANCE', 'TCS', 'HDFCBANK']  # Default fallback
            
#         df = pd.read_csv(universe_file)
#         # Handle different column names - look for ticker or Symbol
#         if 'ticker' in df.columns:
#             return df['ticker'].dropna().tolist()
#         elif 'Symbol' in df.columns:
#             return df['Symbol'].dropna().tolist() 
#         else:
#             # If no standard column names found, try to get first column
#             return df.iloc[:, 0].dropna().tolist()
            
#     except Exception as e:
#         logger.error(f"Error reading universe file: {str(e)}")
#         return ['RELIANCE', 'TCS', 'HDFCBANK']  # Default fallback


def get_company_universe() -> List[str]:
    """Get complete company universe from CSV."""
    try:
        import pandas as pd
        df = pd.read_csv(COMPANY_UNIVERSE_CSV)
        
        if 'Symbol' in df.columns:
            return [symbol.strip() for symbol in df['Symbol'] if symbol and str(symbol).strip()]
        elif 'ticker' in df.columns:
            return [symbol.strip() for symbol in df['ticker'] if symbol and str(symbol).strip()]
        else:
            # Return first column as a fallback
            return [str(row).strip() for row in df.iloc[:, 0] if str(row).strip()]
            
    except Exception as e:
        logger.error(f"Error reading universe CSV: {str(e)}")
        return []


# def check_url_discovery_completed() -> bool:
#     """Check if we can skip URL discovery by looking at existing company_urls.json."""
#     # If company_urls.json doesn't exist, we need to run discovery
#     if not COMPANY_URLS_JSON.exists():
#         return False

#     try:
#         import json
#         with open(COMPANY_URLS_JSON, 'r') as f:
#             urls_data = json.load(f)
            
#         # Get universe symbols
#         universe_symbols = set(get_company_universe())
        
#         # Check how many are already in the URL discovery data
#         discovered_symbols = set(urls_data.keys())
        
#         # If we have all companies discovered, skip further discovery
#         return discovered_symbols >= universe_symbols
        
#     except Exception as e:
#         logger.warning(f"Error checking URL discovery status: {str(e)}")
#         return False


def run_url_discovery() -> None:
    """Run the URL discovery process."""
    logger.info("Starting URL discovery process...")
    
    # Import and run url_discovery module directly
    try:
        # Run with arguments to set limit and overwrite
        import sys
        original_argv = sys.argv[:]
        
        # Add --overwrite flag to force fresh discovery
        sys.argv = ['url_discovery.py', '--overwrite']
        
        url_discovery_main()
        
        # Restore original argv
        sys.argv = original_argv
        
        logger.info("URL discovery process completed successfully")
    except Exception as e:
        logger.error(f"Failed to run URL discovery: {str(e)}")
        raise


# def check_completion_for_symbol(symbol: str) -> bool:
#     """Check if all required files exist for a symbol."""
#     done_path = DONE / f"{symbol}.md"
#     return done_path.exists()


# def inject_run_pipeline(symbols: Optional[List[str]] = None, overwrite: bool = False) -> None:
#     """Run the pipeline process for specified symbols."""
#     from pipeline.pipeline import PipelineRunner
    
#     logger.info(f"Starting pipeline process with {len(symbols) if symbols else 'all'} symbols")
    
#     # Read and parse company URLs
#     try:
#         import json
#         with open(COMPANY_URLS_JSON, 'r') as f:
#             company_urls = json.load(f)
#     except Exception as e:
#         logger.error(f"Error reading company URLs: {str(e)}")
#         raise
    
#     # Filter symbols for processing if needed
#     all_symbols = symbols if symbols is not None else get_company_universe()
    
#     # Create pipeline runner
#     runner = PipelineRunner({
#         'overwrite': overwrite,
#         'output_dir': Path('data')
#     })
    
#     processed_count = 0
    
#     for symbol in all_symbols:
#         try:
#             logger.info(f"Processing symbol: {symbol}")
            
#             # Skip if already completed
#             if not overwrite and check_completion_for_symbol(symbol):
#                 logger.info(f"Symbol {symbol} already completed, skipping")
#                 continue
            
#             # Prepare URL list for this symbol
#             urls = company_urls.get(symbol, {}).get('all_urls', [])
            
#             if not urls:
#                 logger.warning(f"No URLs found for symbol {symbol}, skipping")
#                 continue
            
#             # Run actual document processing using the existing company_crawler logic
#             from Retrieval.Document.document_crawler import process_single_company
#             process_single_company(symbol, urls, overwrite=overwrite)
            
#             processed_count += 1
            
#         except Exception as e:
#             logger.error(f"Error processing symbol {symbol}: {str(e)}")
#             continue
    
#     logger.info(f"Pipeline process completed. Processed {processed_count} symbols")


def run_harvester_pipeline(
    symbols: Optional[List[str]] = None,
    stages: Optional[List[str]] = None,
    overwrite: bool = False,
    limit: Optional[int] = None,
    loop: bool = False,
    loop_interval_hours: int = 24,
    refresh_universe: bool = False,
    use_sandbox: bool = False
) -> None:
    """Main pipeline execution logic with automatic workflow detection."""
    
    # If no explicit arguments provided, run automated bootstrap workflow
    if stages is None and symbols is None and limit is None and not overwrite and not loop:
        logger.info("Running automated bootstrap workflow...")
        
        # First, validate that company_universe.csv exists
        universe_file = Path('config/company_universe.csv')
        if not universe_file.exists():
            logger.error("Error: config/company_universe.csv not found. Please provide the company universe CSV file.")
            sys.exit(1)
            
        # Determine which companies need processing from company_universe.csv
        universe_symbols = get_company_universe()
        
        # Limit to specified count if requested
        if limit and limit > 0:
            universe_symbols = universe_symbols[:limit]
            
        # Check if we already have URL discovery results
        if not check_url_discovery_completed():
            logger.info("Running URL discovery for all companies...")
            
            # Do an initial run of URL discovery
            run_url_discovery()
            
            # Validate URL Discovery and retry any missing or incomplete symbols
            logger.info("Validating URL discovery results...")
            valid_symbols = validate_and_retry_url_discovery(universe_symbols)
            
            # If there were symbols that needed a retry, re-run discovery only on those
            if valid_symbols != set(universe_symbols):
                logger.info(f"Retrying URL discovery for {len(universe_symbols) - len(valid_symbols)} incomplete symbols...")
                
                # Create a temporary CSV with only the missing symbols to be discovered again
                retry_symbols = list(universe_symbols - valid_symbols)
                run_url_discovery_for_symbols(retry_symbols)
        else:
            logger.info("URL discovery already completed, skipping.")
        
        # Run pipeline processing with all universe companies from company_urls.json
        run_pipeline_process(universe_symbols, overwrite=overwrite)
        
        # Check if all universe companies are completed now
        completed_all = True
        for symbol in universe_symbols:
            if not check_completion_for_symbol(symbol):
                completed_all = False
                break
                
        if completed_all and not loop:
            logger.info("All processing completed successfully")
            
            # Final summary validation
            validate_and_print_summary(universe_symbols)
            
            return
        else:
            # Fall through to normal execution mode if we should continue running in a loop or have specified arguments
            pass
    
    else:
        # Fall back to original explicit execution mode
        if stages is None:
            stages = ['discover', 'numeric', 'document', 'convert', 'clean', 'chunk', 'normalize']
            
        if symbols is None:
            # This will be changed to get_company_universe() which returns all valid symbols in universe  
            logger.warning("No specific symbols provided, using all universe symbols.")
            # For now, let's use all companies in the universe
            symbols = get_company_universe()
            
        # Apply limit if specified 
        if limit and limit > 0:
            symbols = symbols[:limit]
            
        for symbol in symbols:
            for stage in stages:
                logger.info(f"Running {stage} stage for {symbol}")
                
                run_stage(stage, symbol, overwrite)


def check_url_discovery_completed() -> bool:
    """Check if we can skip URL discovery by looking at existing company_urls.json."""
    # If company_urls.json doesn't exist, we need to run discovery
    if not COMPANY_URLS_JSON.exists():
        return False

    try:
        import json
        with open(COMPANY_URLS_JSON, 'r') as f:
            urls_data = json.load(f)
            
        # Get universe symbols
        universe_symbols = set(get_company_universe())
        
        # Check how many are already in the URL discovery data
        discovered_symbols = set(urls_data.keys())
        
        # If we have all companies discovered, skip further discovery
        return discovered_symbols >= universe_symbols
        
    except Exception as e:
        logger.warning(f"Error checking URL discovery status: {str(e)}")
        return False


def validate_and_retry_url_discovery(symbols: List[str]) -> Set[str]:
    """Validate discovered URLs and retry discovery on missing or incomplete symbols."""
    
    # Read the discovered symbols from json
    discovered_urls = {}
    try:
        if COMPANY_URLS_JSON.exists():
            with open(COMPANY_URLS_JSON, 'r') as f:
                discovered_urls = json.load(f)
    except Exception as e:
        logger.error(f"Error reading company URLs during validation: {str(e)}")
        return set()  # Return empty set if error
    
    valid_symbols = set()
    
    # Check each symbol for enough URLs
    for symbol in symbols:
        num_urls = len(discovered_urls.get(symbol, {}).get('all_urls', []))
        logger.debug(f"Symbol {symbol}: {num_urls} URLs found")
        
        if num_urls >= 3:
            valid_symbols.add(symbol)
        else:
            logger.info(f"Symbol {symbol} missing or incomplete URLs ({num_urls} < 3)")
            
    return valid_symbols


def run_url_discovery_for_symbols(symbols_to_retry: List[str]) -> None:
    """Run URL discovery specifically on a given list of symbols."""
    
    # Use subprocess to run url_discovery.py with specific symbols
    try:
        cmd = [sys.executable, 'scripts/url_discovery.py', '--overwrite']
        if symbols_to_retry:
            cmd.extend(['--symbols'] + symbols_to_retry)
        logger.info(f"Running discovery retry for {len(symbols_to_retry)} symbols")
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        logger.debug("URL discovery retry completed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to run URL discovery retry: {e.stderr}")


def run_pipeline_process(symbols: List[str], overwrite: bool = False) -> None:
    """Execute the pipeline for specified symbols."""
    # For this implementation, we'll directly create and run the pipeline
    try:
        # Read company URLs
        import json
        with open(COMPANY_URLS_JSON, 'r') as f:
            company_urls = json.load(f)
        
        # Import and run pipeline
        logger.info("Initiating pipeline execution...")
        from pipeline.pipeline import PipelineRunner
        
        runner = PipelineRunner({
            'overwrite': overwrite,
            'output_dir': Path('data')
        })
        
        for symbol in symbols:
            logger.info(f"Processing symbol: {symbol}")
            # Validate symbol exists in URL database
            if symbol not in company_urls:
                logger.warning(f"Symbol {symbol} not found in company_urls.json. Skipping.")
                continue
            
            runner.run([symbol])
            
    except Exception as e:
        logger.error(f"Failed to execute pipeline process: {str(e)}")
        raise


def validate_and_print_summary(symbols: List[str]) -> None:
    """Validate final output files and print a summary report."""
    document_present = 0
    document_missing = 0
    numeric_present = 0
    numeric_missing = 0
    
    missing_docs = []
    missing_numerics = []
    
    done_dir = Path('data/done')
    done_dir.mkdir(exist_ok=True)
    
    for symbol in symbols:
        doc_path = done_dir / f"{symbol}_document.md"
        numeric_path = done_dir / f"{symbol}_numeric.md"
        
        docs_exist = doc_path.exists()
        numerics_exist = numeric_path.exists()

        if docs_exist:
            document_present += 1
        else:
            document_missing += 1
            missing_docs.append(symbol)
            
        if numerics_exist:
            numeric_present += 1
        else:
            numeric_missing += 1
            missing_numerics.append(symbol)
    
    print(f"\nDocument files: {document_present} present, {document_missing} missing.")
    print(f"Numeric files: {numeric_present} present, {numeric_missing} missing.")
    
    if missing_docs:
        print(f"Missing document files for symbols: {', '.join(missing_docs)}")
        
    if missing_numerics:
        print(f"Missing numeric files for symbols: {', '.join(missing_numerics)}")


def run_stage(stage: str, symbol: str, overwrite: bool) -> None:
    """Run a specific stage for a symbol."""
    
    stage_dir = Path(f"data/{stage}")
    stage_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"[{datetime.utcnow().isoformat()}] [START] [{symbol}] {stage} stage")
    
    # Define output paths for each stage
    output_paths = {
        'source': Path('data'),
        'discover': Path(f"data/discovered/{symbol}"),
        'numeric': Path(f"data/cleaned/numeric/{symbol}.json"),
        'document': Path(f"data/cleaned/documents/{symbol}"),
        'convert': Path(f"data/trans/documents/{symbol}"),  # For extracted files
        'clean': Path(f"data/cleaned/numeric/{symbol}.json"),  # This is where clean output goes 
        'chunk': Path(f"data/chunked/{symbol}"),
        'normalize': Path(f"data/normalized/{symbol}/{symbol}.json")
    }
    
    output_path = output_paths.get(stage, Path())
    
    # Check if output exists and skip if not overwriting
    if output_path.exists() or (stage in ['numeric', 'document', 'convert', 'clean', 'chunk', 'normalize'] and 
                                output_path.parent.exists() and output_path.parent.glob('*')):
        if not overwrite:
            logger.info(f"[{datetime.utcnow().isoformat()}] [SKIP] [{symbol}] {stage} stage (output exists)")
            return
            
    try:
        # Execute the appropriate logic for each stage
        if stage == 'source':
            run_source_stage(symbol)
        elif stage == 'discover':
            run_discover_stage(symbol)
        elif stage == 'numeric':
            run_numeric_stage(symbol)
        elif stage == 'document':
            run_document_stage(symbol)
        elif stage == 'convert':
            run_convert_stage(symbol)
        elif stage == 'clean':
            run_clean_stage(symbol)
        elif stage == 'chunk':
            run_chunk_stage(symbol)
        elif stage == 'normalize':
            run_normalize_stage(symbol)
        
        logger.info(f"[{datetime.utcnow().isoformat()}] [DONE] [{symbol}] {stage} stage completed")
        
    except Exception as e:
        logger.error(f"[{datetime.utcnow().isoformat()}] [FAIL] [{symbol}] {stage} stage failed: {str(e)}")
        raise


def run_source_stage(symbol: str) -> None:
    """Run the source stage - builds universe from constituent data."""
    # For this implementation, we assume that build_universe.py is already available
    from scripts.build_universe import build_universe
    
    # In real implementation, you'd call actual universe building logic  
    logger.info("Source stage would build universe")
    pass


def run_discover_stage(symbol: str) -> None:
    """Run URL discovery for a symbol."""
    # This stage would discover URLs from company metadata
    logger.info(f"Discover stage for {symbol}")
    # In real implementation, this would call URL discovery functionality
    pass


def check_completion_for_symbol(symbol: str) -> bool:
    """Check if all required files exist for a symbol."""
    done_path = DONE / f"{symbol}.md"
    return done_path.exists()


def run_numeric_stage(symbol: str) -> None:
    """Run numeric data collection (placeholder for now)."""
    logger.info(f"[Numeric] [{symbol}] processing")
    # This stage would collect financial data from sources
    pass


def run_document_stage(symbol: str) -> None:
    """Run document crawling."""
    logger.info(f"[Document] [{symbol}] processing")
    # This stage would call the actual document crawler logic
    # The actual work is delegated to process_single_company in document_crawler.py
    from Retrieval.Document.document_crawler import run  
    run(symbol)  # Just calling this to make sure the function actually exists
    pass


def run_convert_stage(symbol: str) -> None:
    """Run raw data to structured format conversion."""
    logger.info(f"[Convert] [{symbol}] processing")
    # This stage would convert downloaded files to structured format 
    pass


def run_clean_stage(symbol: str) -> None:
    """Run data cleaning."""
    logger.info(f"[Clean] [{symbol}] processing")
    # This stage would clean the data
    pass


def run_chunk_stage(symbol: str) -> None:
    """Run document chunking."""
    logger.info(f"[Chunk] [{symbol}] processing")
    # This stage would split documents into chunks
    pass


def run_normalize_stage(symbol: str) -> None:
    """Run normalization of data."""
    logger.info(f"[Normalize] [{symbol}] processing")
    # This stage would normalize the data
    pass


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Data Harvester Pipeline')
    
    # Add mutually exclusive group for symbol selection
    symbol_group = parser.add_mutually_exclusive_group(required=True)
    symbol_group.add_argument('--all_symbols', action='store_true',
                              help='Process all symbols from company_urls.json')
    symbol_group.add_argument('--symbol', type=str,
                              help='Process a single symbol from company_urls.json')
    
    parser.add_argument('--stages', nargs='+', 
                       help='Stages to run (source, discover, numeric, document, convert, clean, chunk, normalize)')
    parser.add_argument('--limit', type=int,
                       help='Maximum number of symbols to process')
    parser.add_argument('--overwrite', action='store_true',
                       help='Overwrite existing results')
    parser.add_argument('--loop', action='store_true',
                       help='Run pipeline in a loop')
    parser.add_argument('--loop-interval', type=int, default=24,
                       help='Hours between loops (default: 24)')
    parser.add_argument('--refresh-universe', action='store_true',
                       help='Refresh universe even when looping')
    
    # New arguments for bootstrap workflow
    parser.add_argument('--first-run', action='store_true',
                       help='Initiate the first run bootstrap workflow')
    parser.add_argument('--no-loop', action='store_true',
                       help='Disable loop behavior during first run')
    parser.add_argument('--Retreve_document', action='store_true',
                       help='Include document retrieval step in pipeline') 

    
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    # Create data directory if it doesn't exist
    Path('data').mkdir(exist_ok=True)
    
    args = parse_args()
    
    # Validate --symbol argument if provided
    if args.symbol:
        try:
            with open(COMPANY_URLS_JSON, 'r') as f:
                company_urls = json.load(f)
            
            if args.symbol not in company_urls:
                print(f"Error: Symbol '{args.symbol}' not found in company_urls.json")
                sys.exit(1)
        except Exception as e:
            print(f"Error validating symbol: {str(e)}")
            sys.exit(1)
    
    # Handle --all_symbols vs --symbol
    if args.all_symbols:
        try:
            with open(COMPANY_URLS_JSON, 'r') as f:
                company_urls = json.load(f)
            symbols = list(company_urls.keys())
        except Exception as e:
            print(f"Error reading company_urls.json: {str(e)}")
            sys.exit(1)
    else:
        symbols = [args.symbol]
    
    # Check if first run bootstrap workflow should be initiated
    if args.first_run and args.no_loop and args.Retreve_document:
        logger.info("Initiating first-run bootstrap workflow...")
        
        # Validate company_universe.csv exists as required for this workflow
        universe_file = Path('config/company_universe.csv')
        if not universe_file.exists():
            logger.error("Error: config/company_universe.csv not found. Please provide the company universe CSV file.")
            sys.exit(1)
            
        try:
            run_harvester_pipeline(
                symbols=None,
                stages=None,
                overwrite=False,
                limit=None,
                loop=False,
                loop_interval_hours=24,
                refresh_universe=False
            )
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted by user")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}")
            sys.exit(1)
    else:
        try:
            run_harvester_pipeline(
                symbols=symbols,
                stages=args.stages,
                overwrite=args.overwrite,
                limit=args.limit,
                loop=args.loop,
                loop_interval_hours=args.loop_interval,
                refresh_universe=args.refresh_universe,
                use_sandbox=False  # args.sandbox is commented out
            )
        except KeyboardInterrupt:
            logger.info("Pipeline interrupted by user")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Pipeline failed: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    main()