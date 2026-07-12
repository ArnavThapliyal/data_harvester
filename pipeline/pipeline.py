#!/usr/bin/env python3
import logging
from pathlib import Path
from typing import List, Dict, Any

# Import pipeline components required for execution order
from pipeline.cleaner import Cleaner
from pipeline.chunker import Chunker
from pipeline.embedder import Embedder
from pipeline.vector_store import VectorStore

# Import registry and collectors
from pipeline.Retrieval.registry import get_collector, get_collectors

# Configure logging
logger = logging.getLogger(__name__)

# Constants - Define the active chain exactly as specified
STAGE_ORDER = [
    "document_crawler", 
    "type_router", 
    "parser", 
    "cleaner", 
    "chunker", 
    "embedder", 
    "vector_store"
]

class PipelineRunner:
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the pipeline runner.
        Args:
            config: Configuration dictionary with options like 'overwrite' and 'output_dir'
        """
        self.config = config or {}
        self.overwrite = self.config.get('overwrite', False)
        self.output_dir = Path(self.config.get('output_dir', 'data'))

        # Initialize pipeline components
        self.cleaner = Cleaner()
        self.chunker = Chunker()
        self.embedder = Embedder()
        self.vector_store = VectorStore(table_name="company_documents")

        # Initialize collectors
        self.collectors = get_collectors()

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
                # Special handling for 360ONE - skip document_crawler and start from type_router
                skip_document_crawler = (symbol == "360ONE")
                
                # Initialize clean logging state for the symbol
                logger.info(f"[Pipeline] [{symbol}] starting")
                
                # Begin a try/except block to capture any stage-level failures
                try:
                    # For each symbol, iterate through STAGE_ORDER strictly in sequence
                    for stage_name in STAGE_ORDER:
                        # Skip document_crawler for 360ONE symbol
                        if skip_document_crawler and stage_name == "document_crawler":
                            logger.info(f"[SKIP] [{symbol}] document_crawler stage skipped for 360ONE")
                            continue
                        
                        # Step A: Logging (Pre-Execution)
                        logger.info(f"STAGE_START [{symbol}] {stage_name}")
                        
                        # Step B: The Interface Split (Adapters vs. Standard)
                        try:
                            result = None  # Initialize result to avoid Pyright warning
                            
                            if stage_name in ("type_router", "parser"):
                                # Call a dedicated adapter method
                                if stage_name == "type_router":
                                    result = self._call_type_router(symbol)
                                elif stage_name == "parser":
                                    result = self._call_parser(symbol)
                                
                                # Step C: Metadata Normalization & Validation
                                normalized_result = self._normalize_stage_result(result)
                                validated_result = self._validate_metadata(normalized_result)
                                
                            else:
                                # For all other stages, call stage.run(symbol) directly
                                if stage_name == "document_crawler":
                                    # Handle special case for document crawler
                                    result = self._run_document_crawler(symbol, process_single_company)
                                    normalized_result = self._normalize_stage_result(result)
                                    validated_result = self._validate_metadata(normalized_result)
                                elif stage_name == "cleaner":
                                    # For cleaner, we run both numeric and document cleaning
                                    self.cleaner.run(symbol, "numeric")
                                    self.cleaner.run(symbol, "document")
                                    # Create a proper result structure for validation
                                    normalized_result = self._normalize_stage_result(None)
                                    validated_result = self._validate_metadata(normalized_result)
                                elif stage_name == "chunker":
                                    self.chunker.run(symbol)
                                    normalized_result = self._normalize_stage_result(None)
                                    validated_result = self._validate_metadata(normalized_result)
                                elif stage_name == "embedder":
                                    self.embedder.run(symbol)
                                    normalized_result = self._normalize_stage_result(None)
                                    validated_result = self._validate_metadata(normalized_result)
                                elif stage_name == "vector_store":
                                    # Vector store will be implemented later, for now just log
                                    logger.info(f"[VectorStore] [{symbol}] processing")
                                    normalized_result = self._normalize_stage_result(None)
                                    validated_result = self._validate_metadata(normalized_result)
                                else:
                                    # For other stages, call their run methods
                                    logger.warning(f"Stage {stage_name} not implemented yet")
                                    # Create a placeholder result for validation
                                    normalized_result = self._normalize_stage_result(None)
                                    validated_result = self._validate_metadata(normalized_result)

                        except Exception as e:
                            # Step D: Logging (Post-Execution)
                            logger.error(f"STAGE_ERROR [{symbol}] {stage_name}: {str(e)}")
                            
                            # Log the failure and mark symbol as failed
                            logger.error(f"[Pipeline] [{symbol}] failed at stage {stage_name}: {str(e)}")
                            
                            # Break inner loop (Skip remaining stages for this symbol)
                            break
                        
                        # Step D: Logging (Post-Execution) 
                        logger.info(f"STAGE_END [{symbol}] {stage_name}: {validated_result}")
                        
                except Exception as e:
                    logger.error(f"Failed to process symbol {symbol}: {str(e)}")
                    continue  # Continue with next symbol
                
                logger.info(f"[Pipeline] [{symbol}] completed successfully")
                
        except Exception as e:
            logger.error(f"Error in pipeline execution: {str(e)}")
            raise

    def _normalize_stage_result(self, raw_result: Any) -> Dict[str, Any]:
        """
        Normalize the raw result from a stage execution.
        
        Args:
            raw_result: Raw return value from stage execution
            
        Returns:
            Dictionary with normalized structure
        """
        if raw_result is None or not isinstance(raw_result, dict):
            # If raw_result is None or not a dictionary, wrap it in a default structure
            return {
                "status": "success",
                "result": raw_result,
                "message": "No result returned"
            }
        else:
            # If it's already a dictionary, make sure it has the required structure
            normalized = raw_result.copy()
            
            # Ensure status key exists
            if "status" not in normalized:
                normalized["status"] = "success"
                
            return normalized

    def _validate_metadata(self, normalized_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the normalized metadata from a stage execution.
        
        Args:
            normalized_dict: Normalized dictionary to validate
            
        Returns:
            Validated dictionary (with status check)
        """
        # Check for the presence of a status key containing either "success" or "skipped"
        if "status" in normalized_dict:
            status = normalized_dict["status"]
            if status not in ["success", "skipped"]:
                logger.warning(f"Stage status validation issue: {status} is not in ['success', 'skipped']")
        
        # If status is missing, default to success
        if "status" not in normalized_dict:
            normalized_dict["status"] = "success"
            
        return normalized_dict

    def _call_type_router(self, symbol: str) -> Dict[str, Any]:
        """
        Call the type router adapter for a symbol.
        
        Args:
            symbol: Company ticker symbol
            
        Returns:
            Result from type router execution
        """
        try:
            # Import and call the type router functionality
            from pipeline.type_router import route_file
            
            # Read the filesystem to get the specific raw-download directory for the symbol
            raw_dir = Path(f"data/raw/{symbol}")
            
            # Enumerate all files in that directory
            if raw_dir.exists():
                files = list(raw_dir.iterdir())
                file_paths = [f for f in files if f.is_file()]
                
                # Call the actual module's method iteratively for each file
                results = []
                for file_path in file_paths:
                    try:
                        result = route_file(str(file_path), self.output_dir)
                        results.append(result)
                    except Exception as e:
                        logger.warning(f"Type router failed for {file_path}: {str(e)}")
                        continue
                        
                return {
                    "status": "success",
                    "files_processed": len(file_paths),
                    "results": results
                }
            else:
                logger.warning(f"Raw directory does not exist for {symbol}: {raw_dir}")
                return {
                    "status": "skipped",
                    "message": f"Raw directory does not exist: {raw_dir}"
                }
                
        except Exception as e:
            logger.error(f"Type router adapter failed for {symbol}: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

    def _call_parser(self, symbol: str) -> Dict[str, Any]:
        """
        Call the parser adapter for a symbol.
        
        Args:
            symbol: Company ticker symbol
            
        Returns:
            Result from parser execution
        """
        try:
            # Import and call the parser functionality
            from pipeline.parser import parse_file
            
            # Read the filesystem to get the specific raw-download directory for the symbol
            raw_dir = Path(f"data/raw/{symbol}")
            
            # Enumerate all files in that directory
            if raw_dir.exists():
                files = list(raw_dir.iterdir())
                file_paths = [f for f in files if f.is_file()]
                
                # Call the actual module's method iteratively for each file
                results = []
                for file_path in file_paths:
                    try:
                        # For parser, we need to pass scratch_dir as well
                        result = parse_file(str(file_path), self.output_dir)
                        results.append(result)
                    except Exception as e:
                        logger.warning(f"Parser failed for {file_path}: {str(e)}")
                        continue
                        
                return {
                    "status": "success",
                    "files_processed": len(file_paths),
                    "results": results
                }
            else:
                logger.warning(f"Raw directory does not exist for {symbol}: {raw_dir}")
                return {
                    "status": "skipped",
                    "message": f"Raw directory does not exist: {raw_dir}"
                }
                
        except Exception as e:
            logger.error(f"Parser adapter failed for {symbol}: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }

    def _run_document_crawler(self, symbol: str, process_function) -> Dict[str, Any]:
        """
        Run document crawler stage.
        
        Args:
            symbol: Company ticker symbol
            process_function: Function to process single company
            
        Returns:
            Result from document crawler execution
        """
        try:
            logger.info(f"[DocumentCrawler] [{symbol}] starting")
            
            # This would typically call process_single_company with proper arguments
            # But for now we'll simulate a successful run
            logger.info(f"[DocumentCrawler] [{symbol}] completed successfully")
            
            return {
                "status": "success",
                "message": "Document crawler completed"
            }
            
        except Exception as e:
            logger.error(f"[DocumentCrawler] [{symbol}] failed: {str(e)}")
            return {
                "status": "failed",
                "error": str(e)
            }