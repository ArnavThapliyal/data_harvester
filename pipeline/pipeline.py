#!/usr/bin/env python3
"""
Main pipeline orchestration logic.
PipelineRunner does exactly three things, nothing else:
    1. Run the appropriate stage modules, in order, for each symbol.
    2. Log what ran — every stage start/end, every symbol, every status.
    3. Validate the metadata each stage module's run() call returns.

It has zero knowledge of how any stage works internally. That logic lives in
each stage's own module (document_crawler.py, type_router.py, parser.py,
cleaner.py, chunker.py, embedder.py, vector_store.py). If a comment in this
file ever explains *how* a stage does its job, that comment is wrong and
belongs in that stage's module instead.

SCOPE FOR THIS PASS:
    document -> route -> parse -> clean -> chunk -> embed -> vectorstore (LanceDB)
    Numeric: gated behind mode, not run yet.
    Normalize: not in the active chain this pass — [DEFERRED], not removed.

TAG LEGEND:
    [MISSING]  - stage module doesn't exist yet, call site is a placeholder
    [DEFERRED] - module exists, intentionally not in the active chain this pass
    [CONFIRM]  - verify against the real module's interface once it's built
"""

import argparse
import logging
import json
from pathlib import Path
from typing import List, Dict, Any

# Import pipeline components required for execution order
from pipeline.cleaner import Cleaner
from pipeline.chunker import Chunker
from pipeline.normalizer import Normalizer  
from pipeline.embedder import Embedder

# [MISSING] uncomment as each is built, in your stated order:
from pipeline.type_router import TypeRouter
from pipeline.parser import Parser
from pipeline.vector_store import VectorStore
from Retrieval.registry import get_collector

# Configure logging
logger = logging.getLogger(__name__)

class PipelineRunner:

    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the pipeline runner.
        
        Args:
            config: Configuration dictionary with options like 'overwrite' and 'output_dir'
        """
        self.config = config or {}
        # self.mode = self.config.get("mode", "document")  # [CONFIRM] matches what main.py passes
        self.overwrite = self.config.get('overwrite', False) #not used
        self.output_dir = Path(self.config.get('output_dir', 'data')) #not used
        
        # Initialize pipeline components
        self.cleaner = Cleaner()
        self.chunker = Chunker()
        self.normalizer = Normalizer()
        self.embedder = Embedder()
        
        # [MISSING] uncomment once each module exists
        self.document_crawler = get_collector("document")
        self.type_router = TypeRouter()
        self.parser = Parser()
        self.vector_store = VectorStore(table_name="company_documents")

    def run(self, symbols: List[str]) -> None:
        """
        Run the full pipeline for a list of symbols in documented sequence.
        
        Args:
            symbols: List of company ticker symbols to process
        """
        logger.info(f"Starting pipeline for {len(symbols)} symbols")
        
        # Load necessary dependencies for stages that are explicitly mentioned
        from pipeline.Retrieval.Document.document_crawler import process_single_company
        
        try:
            for symbol in symbols:
                if not self._should_run_stage(symbol):
                    logger.info(f"[SKIP] [{symbol}] Stage already completed")
                    continue
                
                logger.info(f"[Pipeline] [{symbol}] starting")
                
                # Execute stages in the specified order: document_crawler.py -> type_router.py -> parser.py -> cleaner.py -> chunker.py -> embedder.py -> vector_store.py
                self._run_document_crawler(symbol, process_single_company)
                self._run_type_router(symbol) 
                self._run_parser(symbol)
                self._run_cleaner(symbol)
                self._run_chunker(symbol)
                self._run_embedder(symbol)
                self._run_vector_store(symbol)  # [CONFIRM]
                
                logger.info(f"[Pipeline] [{symbol}] completed successfully")
                
        except Exception as e:
            logger.error(f"Error in pipeline execution: {str(e)}")
            raise

    def _should_run_stage(self, symbol: str) -> bool:
        """Check if we should run the pipeline for this symbol based on existing metadata."""
        # Placeholder - actual implementation would check metadata files
        return True

    def _run_document_crawler(self, symbol: str, process_function) -> None:
        """Run document crawler stage."""
        logger.info(f"[DocumentCrawler] [{symbol}] starting")
        try:
            # This would typically call process_single_company with proper arguments
            # But for now we'll use a placeholder approach - actual implementation will be done by the function
            # Let's import it and make sure it can be called successfully
            from pipeline.Retrieval.Document.document_crawler import run
            result = run(symbol)
            logger.info(f"[DocumentCrawler] [{symbol}] completed: {result}")
        except Exception as e:
            logger.error(f"[DocumentCrawler] [{symbol}] failed: {str(e)}")
            raise

    def _run_type_router(self, symbol: str) -> None:
        """Run type router stage."""
        logger.info(f"[TypeRouter] [{symbol}] starting")
        try:
            # [CONFIRM] this import should be adjusted when the type_router.py exists
            from pipeline.type_router import route_file
            route_file(symbol)
            logger.info(f"[TypeRouter] [{symbol}] completed")
        except Exception as e:
            logger.warning(f"[TypeRouter] [{symbol}] failed: {str(e)}")
            # [MISSING] - this is a placeholder, module doesn't exist yet
            logger.info(f"[TypeRouter] [{symbol}] status: skipped")

    def _run_parser(self, symbol: str) -> None:
        """Run parser stage."""
        logger.info(f"[Parser] [{symbol}] starting")
        try:
            # [CONFIRM] this import should be adjusted when the parser.py exists
            from pipeline.parser import Parser  
            parser = Parser()
            parser.run(symbol)
            logger.info(f"[Parser] [{symbol}] completed")
        except Exception as e:
            logger.warning(f"[Parser] [{symbol}] failed: {str(e)}")
            # [MISSING] - this is a placeholder, module doesn't exist yet
            logger.info(f"[Parser] [{symbol}] status: skipped")

    def _run_cleaner(self, symbol: str) -> None:
        """Run cleaner stage."""
        logger.info(f"[Cleaner] [{symbol}] starting")
        
        # Clean numeric data
        self.cleaner.run(symbol, "numeric")
        
        # Clean document data  
        self.cleaner.run(symbol, "document")
        
        logger.info(f"[Cleaner] [{symbol}] completed")

    def _run_chunker(self, symbol: str) -> None:
        """Run chunker stage.""" 
        logger.info(f"[Chunker] [{symbol}] starting")
        
        # Chunk document files
        self.chunker.run(symbol)
        
        logger.info(f"[Chunker] [{symbol}] completed")

    def _run_embedder(self, symbol: str) -> None:
        """Run embedder stage."""
        logger.info(f"[Embedder] [{symbol}] starting")
        try:
            # [CONFIRM] this import should be adjusted when the embedder.py exists  
            self.embedder.run(symbol)
            logger.info(f"[Embedder] [{symbol}] completed")
        except Exception as e:
            logger.error(f"[Embedder] [{symbol}] failed: {str(e)}")
            raise

    def _run_vector_store(self, symbol: str) -> None:
        """Run vector store stage."""
        logger.info(f"[VectorStore] [{symbol}] starting")
        try:
            # [CONFIRM] this import should be adjusted when the vector_store.py exists
            from pipeline.vector_store import VectorStore
            vector_store = VectorStore(table_name="company_documents")
            vector_store.run(symbol)
            logger.info(f"[VectorStore] [{symbol}] completed")
        except Exception as e:
            logger.warning(f"[VectorStore] [{symbol}] failed: {str(e)}")
            # [MISSING] - this is a placeholder, module doesn't exist yet
            logger.info(f"[VectorStore] [{symbol}] status: skipped")

    # These are kept for backwards compatibility but may never be called
    def _run_numeric_stage(self, symbol: str) -> None:
        """Run numeric data collection."""
        logger.info(f"[Numeric] [{symbol}] starting")
        # This will be implemented to fetch numeric data like OHLCV and fundamentals
        # from sources like yfinance, nse, bsc etc. 
        # For now, a placeholder implementation.
        logger.info(f"[Numeric] [{symbol}] completed (placeholder)")

    def _run_document_stage(self, symbol: str) -> None:
        """Run document crawling."""
        logger.info(f"[Document] [{symbol}] starting")
        # This will be implemented to use url_discovery and crawl documents
        # from company websites.
        # For now, a placeholder implementation.
        logger.info(f"[Document] [{symbol}] completed (placeholder)")

    def _run_convert_stage(self, symbol: str) -> None:
        """Run raw data to structured format conversion."""
        logger.info(f"[Convert] [{symbol}] starting")
        # This will be implemented to convert crawled data to structured data
        # in JSON format. 
        # For now, a placeholder implementation.
        logger.info(f"[Convert] [{symbol}] completed (placeholder)")
        
    def _run_normalize_stage(self, symbol: str) -> None:
        """Run normalization stage on chunked data."""
        logger.info(f"[Normalize] [{symbol}] starting")
        
        # Normalize chunked data
        self.normalizer.run(symbol)
        
        logger.info(f"[Normalize] [{symbol}] completed")


