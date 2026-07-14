"""
Chunker for pipeline - splits cleaned text into manageable chunks.

Two-stage split, per the locked architecture decision:
  1. MarkdownHeaderTextSplitter groups text under its nearest header path
     (h1/h2/h3/h4) — this only does anything useful because cleaner.py now
     renders IR header blocks back into '#'-prefixed Markdown lines; before
     that fix this splitter saw one headerless blob per file and the import
     sat unused.
  2. RecursiveCharacterTextSplitter caps each header-section at chunk_size
     characters with overlap_size overlap, so no single chunk blows past
     what's comfortable for one embedding call.

Each output chunk carries `section_path` — its header breadcrumb, e.g.
"Financial Highlights > Segment Revenue". This is what embedder.py's
metadata.section_path used to be [MISSING] for; it now reads it straight
off the chunk dict.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from config.settings import CLEANED_DOCUMENTS, CHUNKED

logger = logging.getLogger(__name__)

HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]


class Chunker:
    """Chunker that processes cleaned document text and splits into manageable pieces."""

    def __init__(self):
        self.chunk_size = 1000  # characters per chunk
        self.overlap_size = 100  # overlapping characters between chunks
        self._header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=HEADERS_TO_SPLIT_ON,
            strip_headers=False,  # keep header text inside chunk content too —
                                   # it's retrieval-relevant, not just routing metadata
        )
        self._char_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.overlap_size,
        )

    def run(self, symbol: str) -> Dict[str, Any]:
        """
        [DEBUG/legacy path] Re-chunk already-cleaned .txt files from disk.
        Not part of the active index stage — indexer.py calls chunk_text()
        directly on in-memory text instead. Kept for standalone re-chunking
        without re-parsing/re-embedding (e.g. after tuning chunk_size).
        """
        input_dir = CLEANED_DOCUMENTS / symbol
        output_dir = CHUNKED / symbol

        if not input_dir.exists():
            logger.warning(f"[chunker] [{symbol}] no cleaned input found at {input_dir}")
            return {"status": "no_data", "chunks_written": 0}

        output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"[chunker] [{symbol}] starting chunking")

        files_processed = 0
        total_chunks = 0
        for file_path in sorted(input_dir.iterdir()):
            if file_path.is_file() and file_path.suffix == ".txt":
                total_chunks += self._chunk_file(file_path, output_dir)
                files_processed += 1

        logger.info(
            f"[chunker] [{symbol}] completed chunking — "
            f"{total_chunks} chunks across {files_processed} file(s)"
        )

        if files_processed == 0:
            return {"status": "no_data", "chunks_written": 0}
        return {"status": "success", "chunks_written": total_chunks, "files_processed": files_processed}

    def chunk_text(self, content: str) -> List[Dict[str, Any]]:
        """
        Pure in-memory chunking: cleaned Markdown text in, chunk dicts out.
        No disk I/O — this is what indexer.py calls directly. header-split
        then char-split, same two-stage logic _chunk_file used to inline;
        _chunk_file below now just calls this and writes the result.
        """
        if not content.strip():
            return []

        sections = self._header_splitter.split_text(content)

        chunks: List[Dict[str, Any]] = []
        chunk_id = 0
        for section in sections:
            section_path = " > ".join(v for v in section.metadata.values() if v) if section.metadata else ""

            for sub_text in self._char_splitter.split_text(section.page_content):
                if not sub_text.strip():
                    continue
                chunks.append({
                    "chunk_id": chunk_id,
                    "content": sub_text,
                    "section_path": section_path,
                })
                chunk_id += 1

        return chunks

    def _chunk_file(self, file_path: Path, output_dir: Path) -> int:
        """[DEBUG/legacy path] Chunk one cleaned .txt file, write result to disk. Returns chunk count."""
        content = file_path.read_text()
        chunks = self.chunk_text(content)

        if not chunks:
            return 0

        chunk_data = {"original_file": file_path.name, "chunks": chunks}
        output_file = output_dir / f"{file_path.stem}_chunks.json"
        with open(output_file, 'w') as f:
            json.dump(chunk_data, f, indent=2)

        return len(chunks)
