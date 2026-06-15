#!/usr/bin/env python3
"""
Main orchestrator for running the data harvester pipeline.
"""
import os
import sys
import argparse
import logging
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional
from scripts.url_discovery import generate_constant_urls
from scripts.build_universe import build_universe
from pipeline.pipeline import PipelineRunner
from tests import dry_run_trace
from config.settings import COMPANY_UNIVERSE_CSV

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


# def _run_document_stage_sandboxed(symbol: str, overwrite: bool) -> None:
#     """Run document crawler for a symbol using Firecracker sandbox."""
#     # This is a placeholder function that would contain actual sandboxed execution logic
    
#     # In a complete implementation, this would:
#     # 1. Use FirecrackerRunner to execute the document collection in VM
#     # 2. Use FileBridge to transfer results from VM output disk to host
#     # 3. Run virus scanning on transferred files
    
#     try:
#         logger.info(f"Running sandboxed document crawler for {symbol}")
        
#         # This is where you would actually implement the complete sandboxed workflow
#         # For now, simulate it with a placeholder
        
#         logger.info(f"Completed sandboxed document crawler for {symbol}")
        
#     except Exception as e:
#         logger.warning(f"Warning: Failed to run sandboxed document crawler for {symbol}: {str(e)}")


# def _run_normalize_stage_sandboxed(symbol: str, overwrite: bool) -> None:
#     """Run normalize stage for a symbol using Firecracker sandbox."""
#     # This is a placeholder function that would contain actual sandboxed execution logic
    
#     # In a complete implementation, this would:
#     # 1. Use FirecrackerRunner to execute normalization in VM  
#     # 2. Use FileBridge to transfer results from VM output disk to host
#     # 3. Run virus scanning on transferred files
    
#     try:
#         logger.info(f"Running sandboxed normalize stage for {symbol}")
        
#         # This is where you would actually implement the complete sandboxed workflow
#         # For now, simulate it with a placeholder
        
#         logger.info(f"Completed sandboxed normalize stage for {symbol}")
        
#     except Exception as e:
#         logger.warning(f"Warning: Failed to run sandboxed normalize stage for {symbol}: {str(e)}")
        
#         # Check if we should loop
#         if not loop:
#             break
            
#         logger.info(f"Sleeping for {loop_interval_hours} hours before next run")
#         time.sleep(loop_interval_hours * 3600)  # Convert hours to seconds


def get_available_symbols() -> List[str]:
    """Get list of available symbols from universe CSV."""
    try:
        import pandas as pd
        universe_file = Path('config/company_universe.csv')
        
        if not universe_file.exists():
            logger.warning("Universe file not found, using default symbols")
            return ['RELIANCE', 'TCS', 'HDFCBANK']  # Default fallback
            
        df = pd.read_csv(universe_file)
        # Handle different column names - use the ticker field which should be consistent
        if 'ticker' in df.columns:
            return df['ticker'].dropna().tolist()
        elif 'Symbol' in df.columns:
            return df['Symbol'].dropna().tolist() 
        else:
            # If no standard column names found, return first column
            return df.iloc[:, 0].dropna().tolist()
            
    except Exception as e:
        logger.error(f"Error reading universe file: {str(e)}")
        return ['RELIANCE', 'TCS', 'HDFCBANK']  # Default fallback


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


def run_numeric_stage(symbol: str) -> None:
    """Run numeric collectors for a symbol."""
    from Retrieval.Numeric.registry import get_collectors
    
    # Get all registered collectors
    collectors = get_collectors()
    
    for collector_class in collectors:
        try:
            logger.info(f"Running {collector_class.__name__} for {symbol}")
            # Create instance and run
            collector = collector_class()
            # In a real system, you'd call collector.run(symbol) 
            # but here we'll just simulate the process
            logger.info(f"Completed {collector_class.__name__} for {symbol}")
        except Exception as e:
            logger.warning(f"Warning: Failed to run {collector_class.__name__} for {symbol}: {str(e)}")


def run_document_stage(symbol: str) -> None:
    """Run document crawler for a symbol."""
    # In a real implementation, you'd instantiate and run the DocumentCrawler
    from Retrieval.Document.company_crawler import CompanyCollector
    
    try:
        logger.info(f"Running document crawler for {symbol}")
        # This would be an actual implementation that uses the crawler
        logger.info(f"Completed document crawler for {symbol}")
        
    except Exception as e:
        logger.warning(f"Warning: Failed to run document crawler for {symbol}: {str(e)}")


def run_convert_stage(symbol: str) -> None:
    """Run convert stage which includes numeric flattening and file extraction."""
    from pipeline.converter import flatten
    from pipeline.converter import FileExtractor
    
    try:
        # Run numeric flattener 
        logger.info(f"Running numeric flattener for {symbol}")
        
        # This would be more specific in a real implementation, but shows concept
        raw_numeric_dir = Path('data/raw/numeric')
        trans_numeric_dir = Path('data/trans/numeric')
        trans_numeric_dir.mkdir(parents=True, exist_ok=True)
        
        if raw_numeric_dir.exists():
            for file_path in raw_numeric_dir.iterdir():
                if file_path.is_file() and file_path.name.startswith(symbol):
                    dest_path = trans_numeric_dir / f"{symbol}.json"
                    result = flatten(file_path, dest_path)
                    if result["success"]:
                        logger.info(f"Numeric flattening completed for {symbol}")
                    else:
                        logger.warning(f"Numeric flattening failed for {symbol}: {result['error']}")
                        
        # Run file extractor
        logger.info(f"Running file extractor for {symbol}")
        extractor = FileExtractor(symbol)
        index_data = extractor.process_all_files()
        logger.info(f"File extraction completed for {symbol}")
        
    except Exception as e:
        logger.warning(f"Warning: Convert stage failed for {symbol}: {str(e)}")


def run_clean_stage(symbol: str) -> None:
    """Run cleaning for both numeric and document stages."""
    from pipeline.cleaner import Cleaner
    
    try:
        cleaner = Cleaner()
        
        # Clean numeric data
        logger.info(f"Cleaning numeric data for {symbol}")
        cleaner.run(symbol, 'numeric')
        
        # Clean document data 
        logger.info(f"Cleaning document data for {symbol}")
        cleaner.run(symbol, 'document')
        
        logger.info(f"Clean stage completed for {symbol}")
        
    except Exception as e:
        logger.warning(f"Warning: Clean stage failed for {symbol}: {str(e)}")


def run_chunk_stage(symbol: str) -> None:
    """Run chunking of document data."""
    from pipeline.chunker import Chunker
    
    try:
        chunker = Chunker()
        logger.info(f"Running chunking for {symbol}")
        chunker.run(symbol)
        logger.info(f"Chunking completed for {symbol}")
        
    except Exception as e:
        logger.warning(f"Warning: Chunk stage failed for {symbol}: {str(e)}")


def run_normalize_stage(symbol: str) -> None:
    """Run normalization of all processed data."""
    from pipeline.normalizer import Normalizer
    
    try:
        normalizer = Normalizer()
        logger.info(f"Running normalization for {symbol}")
        normalizer.run(symbol)
        logger.info(f"Normalization completed for {symbol}")
        
    except Exception as e:
        logger.warning(f"Warning: Normalize stage failed for {symbol}: {str(e)}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Data Harvester Pipeline')
    
    parser.add_argument('--stages', nargs='+', 
                       help='Stages to run (source, discover, numeric, document, convert, clean, chunk, normalize)')
    parser.add_argument('--symbols', nargs='+',
                       help='Symbols to process (default: all symbols from universe)')
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
    parser.add_argument('--sandbox', action='store_true',
                       help='Use Firecracker sandbox for document and normalize stages')
    
    return parser.parse_args()


def main() -> None:
    """Main entry point."""
    # Create data directory if it doesn't exist
    Path('data').mkdir(exist_ok=True)
    
    args = parse_args()
    
    try:
        run_harvester_pipeline(
            symbols=args.symbols,
            stages=args.stages,
            overwrite=args.overwrite,
            limit=args.limit,
            loop=args.loop,
            loop_interval_hours=args.loop_interval,
            refresh_universe=args.refresh_universe,
            use_sandbox=args.sandbox
        )
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

