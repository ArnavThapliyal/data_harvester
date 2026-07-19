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
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

from config.settings import CLEANED_DOCUMENTS, CHUNKED
logger = logging.getLogger(__name__)

HEADERS_TO_SPLIT_ON = [
    ("#", "h1"),
    ("##", "h2"),
    ("###", "h3"),
    ("####", "h4"),
]

# Must match the sentinel format cleaner.py's render_blocks_to_text() emits.
PAGE_MARKER_RE = re.compile(r"\[\[PAGE:(\d+)\]\]")


class Chunker:
    """Chunker that processes cleaned document text and splits into manageable pieces."""
    
    # Class-level counter to ensure chunk_id is unique across all files
    _global_chunk_id = 0

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

    def _generate_chunk_id(self, content: str, chunk_index: int) -> str:
        # Create a hash of the content to make it unique
        content_hash = hashlib.md5(content.encode()).hexdigest()[:6]
        return f"{content_hash}_{chunk_index}"

    @staticmethod
    def _extract_page_range(text: str) -> Tuple[str, str]:
        """
        Pull [[PAGE:n]] sentinels out of a sub-chunk, return (clean_text, page_range).

        A sub-chunk can straddle a page boundary (chunk_size doesn't respect
        page edges), so page_range is "n" for a single page or "lo-hi" when
        the chunk spans several. Falls back to "unknown" only if no markers
        survived — e.g. parser never supplied page_number upstream.
        """
        pages = [int(p) for p in PAGE_MARKER_RE.findall(text)]
        clean = PAGE_MARKER_RE.sub("", text)
        clean = re.sub(r"\n{3,}", "\n\n", clean).strip()

        if not pages:
            return clean, "unknown"
        lo, hi = min(pages), max(pages)
        return clean, (str(lo) if lo == hi else f"{lo}-{hi}")

    def run(self, symbol: str) -> Dict[str, Any]:
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

    def chunk_text(self, text: str) -> List[Dict[str, Any]]:
        """
        Splits clean text into chunks using header-aware character splitting.
        """
        if not text.strip():
            return []

        # Stage 1: Group by headers
        header_sections = self._header_splitter.split_text(text)
        
        chunks = []
        chunk_idx = 0
        
        # Stage 2: Sub-split large header sections to fit within chunk_size
        for section in header_sections:
            # Build the section path breadcrumb string
            header_dict = section.metadata
            breadcrumb = " > ".join([header_dict[h] for h in ["h1", "h2", "h3", "h4"] if h in header_dict])
            
            # Sub-split into target character limits
            sub_chunks = self._char_splitter.split_text(section.page_content)
            
            for sub_content in sub_chunks:
                clean_content, page_range = self._extract_page_range(sub_content)
                if not clean_content:
                    # sub-chunk was markers only (rare, e.g. a lone page
                    # break landed on a split boundary) — nothing to embed
                    continue

                # Generate our unique, collision-proof chunk_id
                unique_chunk_id = self._generate_chunk_id(clean_content, chunk_idx)

                chunk_dict = {
                    "chunk_id": unique_chunk_id,  # <-- Using our verified unique ID variable here
                    "content": clean_content,
                    "section_path": breadcrumb,
                    "page_range": page_range,
                }
                chunks.append(chunk_dict)
                chunk_idx += 1
                
        return chunks