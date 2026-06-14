"""Entry point for running a collector pipeline."""

import argparse
import sys
from pathlib import Path

# Add the project root to Python path so we can import modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import COMPANY_UNIVERSE_CSV
from Retrieval.Numeric.indiaapi_collector import IndiaAPICollector


def main():
    """Main entry point for the collection pipeline."""
    
    parser = argparse.ArgumentParser(description="Run data harvesting pipeline")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-fetch symbols even when a JSON file already exists"
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=None,
        help="Directory for per-symbol JSON files and manifest.json"
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=3.0,
        help="Seconds to wait between API requests"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N symbols (for testing)"
    )
    
    args = parser.parse_args()
    
    print("Initializing India API collector...")
    
    # Create collector instance
    collector = IndiaAPICollector(
        raw_dir=args.raw_dir,
        overwrite=args.overwrite,
        rate_limit_seconds=args.rate_limit
    )
    
    # Run collection on universe symbols (or limited subset if --limit is provided)
    symbols = None
    if args.limit:
        symbols = collector.read_symbols()[:args.limit]
    
    print(f"Starting collection of {len(symbols) if symbols else 'all'} symbols...")
    
    try:
        import asyncio
        asyncio.run(collector.run_async(symbols=symbols))
        print("Collection completed successfully!")
        
    except Exception as e:
        print(f"Error during collection: {e}")
        raise


if __name__ == "__main__":
    main()