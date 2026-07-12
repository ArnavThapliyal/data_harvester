"""
Indexer — the entire raw-file-to-vector-row path, collapsed into one
in-memory pipeline per file.

There is no data/transient/, data/cleaned/, data/chunked/, or
data/embedded/ in this path anymore. Those directories only ever existed
to hand data between what used to be five separate pipeline stages
(type_router, parser, cleaner, chunker, embedder) each reading a directory
the previous one wrote. Collapsed into one Python call stack, that handoff
is just passing a variable to the next function — parse() returns
ir_blocks, clean() takes ir_blocks and returns text, chunk() takes text and
returns chunk dicts, embed() takes chunk dicts and returns them with
vectors attached. Nothing touches disk in between.

The only disk I/O in this file is: reading the raw document (already on
disk courtesy of document_crawler), and the one upsert_chunks() call at
the very end. That call is a single LanceDB merge_insert().execute() — one
commit — so per-file atomicity falls out for free: if parsing, cleaning,
chunking, or embedding raises anywhere above it, upsert_chunks() is never
reached and the table is untouched for that file. No version-snapshot /
rollback bookkeeping needed; there's nothing to roll back.

Granularity is per FILE, not per symbol: index_symbol() iterates a
symbol's raw files and calls _index_file() once per file, so one bad PDF
in a batch of twelve doesn't touch the other eleven's already-committed
rows, and doesn't stop them from being indexed either.
"""
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from config.settings import RAW_DOCUMENTS, SCRATCH_DIR
from pipeline.type_router import route_file
from pipeline.parser import Parser
from pipeline.cleaner import Cleaner
from pipeline.chunker import Chunker
from pipeline.embedder import embed_chunks
from pipeline.vector_store import upsert_chunks, TABLE_NAME

logger = logging.getLogger(__name__)


class Indexer:
    """
    index_symbol(symbol) is pipeline.py's one call for turning a symbol's
    downloaded raw files into rows in LanceDB. Pass raw_dir= to point it at
    an arbitrary folder instead of the symbol's default location under
    config.settings.RAW_DOCUMENTS — useful for testing against a handful of
    files without touching the real data/raw/ tree.
    """

    def __init__(self):
        self._parser = Parser()
        self._cleaner = Cleaner()
        self._chunker = Chunker()

    def index_symbol(self, symbol: str, raw_dir: Optional[Path] = None) -> Dict[str, Any]:
        raw_dir = raw_dir or (RAW_DOCUMENTS / symbol)
        if not raw_dir.exists():
            logger.warning(f"[indexer] [{symbol}] no raw input found at {raw_dir}")
            return {"status": "no_data", "files_indexed": 0}

        SCRATCH_DIR.mkdir(parents=True, exist_ok=True)  # route_file needs somewhere to extract zips

        files_indexed = 0
        files_failed = 0
        files_skipped = 0
        chunks_written = 0

        for file_path in sorted(raw_dir.iterdir()):
            # manifest.json is document_crawler's own bookkeeping, not a document.
            if not file_path.is_file() or file_path.name == "manifest.json":
                continue

            routed = route_file(str(file_path), SCRATCH_DIR)
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

                try:
                    n = self._index_file(Path(resolved_path), symbol, source_filename=file_path.name)
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

    def _index_file(self, file_path: Path, symbol: str, source_filename: str) -> int:
        """
        parse -> clean -> chunk -> embed -> upsert for ONE file, entirely
        in memory until the final upsert_chunks() call. Returns the number
        of chunks written (0 on an empty/unparseable file — that's a
        content problem, handled as files_failed by the caller, not an
        exception). Real failures (docling errors, embedding errors)
        propagate up to index_symbol()'s per-file try/except instead of
        being swallowed here.
        """
        ir_blocks = self._parser.run(str(file_path), SCRATCH_DIR)
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
            chunk["metadata"] = {
                "symbol": symbol,
                "source_filename": source_filename,
                "doc_type": "unknown",  # [MISSING] — DocumentClassifier lives in normalizer.py, [DEFERRED]
                "downloaded_at": now,   # embed time, not actual download time — [CONFIRM]
                "source_url": "",       # [MISSING] — document_crawler's manifest.json has this per
                                        # file (url <-> file mapping); not threaded through here yet
                "section_path": chunk.get("section_path", ""),
                "page_range": "",       # [MISSING] — lost when cleaner flattens IR blocks to text
            }

        embedded = embed_chunks(chunks)  # dedups + reuses cached vectors via the sqlite content_hash cache
        return upsert_chunks(embedded, table_name=TABLE_NAME)
