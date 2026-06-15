"""Main pipeline orchestration logic."""

import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any
from .collectors import BaseCollector, NumericCollector, DocumentCollector
from .documents import CollectedDocument
from .storage import StorageProvider
from Retrieval.registry import get_numeric_collector, get_document_collector
from Retrieval.Document.document_crawler import process_symbol_urls
from pipeline.cleaner import Cleaner
from pipeline.chunker import Chunker
from pipeline.normalizer import Normalizer
from pipeline.exporter import Exporter
from pipeline.storage import Storage
from pipeline.utils import get_available_symbols
from pipeline.collectors import get_collectors
from pipeline.documents import get_documents

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Main pipeline orchestrator that coordinates all Retrieval and storage."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.storage = StorageProvider(config)
        self.collectors: List[BaseCollector] = []
        
    def add_collector(self, collector: BaseCollector):
        """Add a collector to the pipeline."""
        self.collectors.append(collector)
        
    def run(self):
        """Execute the full data collection and processing pipeline."""
        logger.info("Starting pipeline execution")
        
        # Run each collector in sequence
        for collector in self.collectors:
            try:
                logger.info(f"Running collector: {collector.__class__.__name__}")
                records = collector.collect()
                
                # Validate collected data 
                if not collector.validate(records):
                    logger.warning(f"Validation failed for {collector.__class__.__name__}")
                    continue
                    
                # Normalize if it's a numeric collector
                if isinstance(collector, NumericCollector):
                    records = collector.normalize(records)
                    
                # Store the results
                self._store_records(collector, records)
                
            except Exception as e:
                logger.error(f"Error running {collector.__class__.__name__}: {e}")
                continue
                
        logger.info("Pipeline execution completed")
        
    def _store_records(self, collector: BaseCollector, records: List[Dict[str, Any]]):
        """Store collected records using the storage provider."""
        logger.info(f"Storing {len(records)} records from {collector.__class__.__name__}")
        self.storage.store_collected_data(collector, records)


def main():
    """Main entry point for the pipeline."""
    parser = argparse.ArgumentParser(description="Run the data harvesting pipeline")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/output"),
        help="Output directory for collected data"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup basic configuration
    logging.basicConfig(
        level=logging.INFO if not args.verbose else logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create pipeline runner
    config = {
        "output_dir": args.output_dir,
        "verbose": args.verbose
    }
    
    runner = PipelineRunner(config)
    
    # Add your collectors here (this is just an example)
    # For now, we can just run a basic test
    logger.info("Pipeline initialized. Add specific collector instances to process.")
    
    return runner


if __name__ == "__main__":
    pipeline = main()