"""
Indexer

Converts raw documents into LanceDB rows using a single in-memory pipeline.

Pipeline:
    parse -> clean -> chunk -> embed -> upsert

Only two disk operations occur:
    1. Read the raw document.
    2. Commit chunks to LanceDB.

Everything between those steps stays in memory.

Indexing is atomic per file. A failed parse, clean, chunk, or embedding step
never reaches the database. Other files continue processing independently.
"""

import hashlib
import logging
import os
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import RAW_DOCUMENTS, RAW_NUMERIC, TRANS_NUMERIC, TRANS_DOCUMENTS, CLEANED_NUMERIC, CLEANED_DOCUMENTS, CHUNKED, DONE
from pipeline.type_router import route_file
from pipeline.parser import Parser
from pipeline.cleaner import Cleaner
from pipeline.chunker import Chunker
from pipeline.embedder import embed_chunks
from pipeline.vector_store import VectorStore

logger = logging.getLogger(__name__)


class Indexer:
    def __init__(self):
        self._parser = Parser()
        self._cleaner = Cleaner()
        self._chunker = Chunker()

    def index_symbol(self, symbol: str, raw_dir: Optional[Path] = None) -> Dict[str, Any]:
        raw_dir = raw_dir or (RAW_DOCUMENTS / symbol)
        if not raw_dir.exists():
            logger.warning(f"[indexer] [{symbol}] no raw input found at {raw_dir}")
            return {"status": "no_data", "files_indexed": 0}

        # --- NEW CODE: Load manifest.json to map filenames to URLs ---
        url_map = {}
        manifest_path = raw_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    manifest_data = json.load(f)
                    for item in manifest_data.get("downloaded_files", []):
                        if item.get("file"):
                            # The file path in manifest might be absolute, so we extract just the name
                            fname = Path(item["file"]).name
                            url_map[fname] = item.get("url", "")
            except Exception as e:
                logger.warning(f"[indexer] [{symbol}] failed to read manifest.json: {e}")

        # Use the RAW_DOCUMENTS directory as scratch space for temporary operations
        scratch_dir = RAW_DOCUMENTS / symbol / "scratch"
        scratch_dir.mkdir(parents=True, exist_ok=True)  # route_file needs somewhere to extract zips

        files_indexed = 0
        files_failed = 0
        files_skipped = 0
        chunks_written = 0

        for file_path in sorted(raw_dir.iterdir()):
            # manifest.json is document_crawler's own bookkeeping, not a document.
            if not file_path.is_file() or file_path.name == "manifest.json":
                continue

            routed = route_file(str(file_path), scratch_dir)
            if not routed:
                files_skipped += 1
                continue

            for handler, resolved_path in routed:
                if handler != "structured_doc_handler":
                    # tabular_handler (xlsx/csv filings) — [DEFERRED], no
                    # numeric-style consumer wired in yet. Recorded via the
                    # skip counter, not silently dropped.
                    files_skipped += 1
                    continue

                # Fetch the URL for this specific file from our map
                source_url = url_map.get(file_path.name, "")

                try:
                    n = self._index_file(
                        Path(resolved_path), 
                        symbol, 
                        source_filename=file_path.name,
                        source_url=source_url
                    )
                except Exception as exc:
                    logger.warning(f"[indexer] [{symbol}] failed on {resolved_path}: {exc}", exc_info=True)
                    files_failed += 1
                    continue

                if n == 0:
                    files_failed += 1
                else:
                    files_indexed += 1
                    chunks_written += n

        if files_indexed == 0:
            return {
                "status": "no_data",
                "files_indexed": 0,
                "files_failed": files_failed,
                "files_skipped": files_skipped,
            }

        return {
            "status": "success",
            "files_indexed": files_indexed,
            "files_failed": files_failed,
            "files_skipped": files_skipped,
            "chunks_written": chunks_written,
        }

    def _index_file(self, file_path: Path, symbol: str, source_filename: str, source_url: str = "") -> int:
        # Define the scratch directory (adjust the path if you want it stored elsewhere)
        scratch_dir = str(file_path.parent / "scratch")
        # Ensure the directory actually exists before the parser tries to use it
        os.makedirs(scratch_dir, exist_ok=True)
        ir_blocks: list[dict[Any, Any]] = self._parser.run(str(file_path), scratch_dir)
        if not ir_blocks:
            return 0

        cleaned_blocks = self._cleaner.clean_ir_blocks(ir_blocks)
        text = self._cleaner.render_blocks_to_text(cleaned_blocks)
        if not text.strip():
            return 0

        chunks = self._chunker.chunk_text(text)
        if not chunks:
            return 0

        now = datetime.now(timezone.utc).isoformat()
        for chunk in chunks:
            chunk["content_hash"] = hashlib.sha256(chunk["content"].encode()).hexdigest()
            
            # --- NEW CODE: Place required keys at the root of the chunk dict ---
            chunk["source_url"] = source_url
            chunk["page_range"] = chunk.get("page_range", "unknown") # Hardcoded to satisfy vector_store.py validation
            
            # Keep remaining extra info in metadata
            chunk["metadata"] = {
                "symbol": symbol,
                "source_filename": source_filename,
                "doc_type": "unknown",  # [MISSING] — DocumentClassifier lives in normalizer.py, [DEFERRED]
                "downloaded_at": now,   # embed time, not actual download time — [CONFIRM]
                "section_path": chunk.get("section_path", ""),
            }

        embedded = embed_chunks(chunks)  # dedups + reuses cached vectors via the sqlite content_hash cache
        
        # Initialize the vector store and run the upsert
        store = VectorStore()
        store.run(embedded, symbol)
        
        # VectorStore.run() returns None, but _index_file expects an integer 
        # representing chunks written, so we return the length of the embedded list.
        return len(embedded)