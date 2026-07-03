import logging

logger = logging.getLogger(__name__)

class DataPipeline:
    def __init__(self, config):
        self.config = config
        self.cleaner = None  # Placeholder, to be initialized properly in real implementation
        self.parser = None
        self.vector_store = None

    def _run_parser(self, symbol):
        try:
            from pipeline.parser import Parser
            parser = Parser()
            return parser.parse(symbol)
        except ImportError:
            logger.warning("[MISSING] parser module not found, skipping.")
            return {"status": "skipped", "reason": "parser missing"}

    def _run_vector_store(self, symbol):
        try:
            from pipeline.vector_store import VectorStore
            vector_store = VectorStore()
            return vector_store.store(symbol)
        except ImportError:
            logger.warning("[MISSING] vector_store module not found, skipping.")
            return {"status": "skipped", "reason": "vector_store missing"}

    def _run_cleaner(self, symbol):
        # Gate cleaner execution based on mode or context
        if self.config.get('process_numeric', False): 
            return self.cleaner.run(symbol, "numeric")
        else:
            logger.info("Numeric processing not enabled, skipping cleaner for numeric data.")
            return {"status": "skipped", "reason": "numeric processing disabled"}

    def run(self, symbol):
        # Run components in sequence
        parser_result = self._run_parser(symbol)
        vector_store_result = self._run_vector_store(symbol)
        cleaner_result = self._run_cleaner(symbol)

        return {
            "symbol": symbol,
            "parser": parser_result,
            "vector_store": vector_store_result,
            "cleaner": cleaner_result
        }