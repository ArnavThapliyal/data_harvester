"""
Cleaner for pipeline - cleans both numeric and document data.

DOCUMENT MODE:
    Reads parser output (IR blocks) from data/transient/documents/{symbol}/*.json,
    strips boilerplate/headers/footers, and writes plain text to
    data/cleaned/documents/{symbol}/*.txt.

    Output is .txt, not .json — chunker.py only reads .txt files from its
    input directory, so cleaner's output format is dictated by chunker's
    input contract. Header blocks are rendered back to '#'-prefixed
    Markdown lines (see _render_blocks_to_text) instead of being flattened
    to bare text — chunker.py's MarkdownHeaderTextSplitter has nothing to
    split on otherwise. Page-number/block-type provenance beyond that is
    still discarded here; if that needs to survive into the vector store,
    chunker.py needs to change too.

NUMERIC MODE:
    Unchanged from before, still [DEFERRED] from pipeline.py's active chain.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set
import logging
from collections import Counter

from config.settings import TRANS_DOCUMENTS, CLEANED_DOCUMENTS, TRANS_NUMERIC, CLEANED_NUMERIC

logger = logging.getLogger(__name__)


class Cleaner:
    """Cleaner for pipeline that handles both numeric and document data cleaning."""

    # Static denylist for boilerplate text. Entries with regex metacharacters
    # are compiled and matched with fullmatch(); plain-string entries are
    # matched via exact set membership. (Previously, regex entries were
    # silently dropped from matching entirely — see _static_regex_patterns.)
    DENYLIST_PATTERNS = [
        "Scanned with CamScanner",
        "Powered by",
        "Confidential",
        "Copyright",
        "All rights reserved",
        r"Page \d+ of \d+",   # Page X of Y pattern
        r"^[._-]{5,}$",       # Lines with 5+ dashes/underscores/dots
    ]

    def __init__(self):
        pass

    def run(self, symbol: str, mode: str) -> Dict[str, Any]:
        """
        Run cleaning process for a symbol in either numeric or document mode.

        Args:
            symbol: Company ticker symbol
            mode: Either 'numeric' or 'document'

        Returns:
            {"status": "success" | "no_data", ...counts}
        """
        if mode == "numeric":
            result = self._clean_numeric(symbol)
        elif mode == "document":
            result = self._clean_document(symbol)
        else:
            raise ValueError(f"Unknown mode: {mode}")

        logger.info(f"[cleaner] [{symbol}] mode={mode} — {result}")
        return result

    # ---- numeric mode -----------------------------------------------------

    def _clean_numeric(self, symbol: str) -> Dict[str, Any]:
        """Clean numeric data (OHLCV and fundamentals). [DEFERRED] from the active chain."""
        input_path = TRANS_NUMERIC / f"{symbol}.json"
        output_path = CLEANED_NUMERIC / f"{symbol}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not input_path.exists():
            logger.warning(f"[cleaner] [{symbol}] numeric input not found: {input_path}")
            return {"status": "no_data", "rows_cleaned": 0}

        with open(input_path, 'r') as f:
            data = json.load(f)

        cleaned_ohlcv = []
        seen_dates = set()

        if "ohlcv" in data and isinstance(data["ohlcv"], list):
            for row in data["ohlcv"]:
                if row.get("close") is None or row.get("close", 0) <= 0:
                    continue
                date_str = row.get("date")
                if not date_str or not self._is_valid_date_format(date_str):
                    continue
                if date_str in seen_dates:
                    continue
                seen_dates.add(date_str)
                cleaned_ohlcv.append(row)

        cleaned_ohlcv.sort(key=lambda x: x.get("date", ""))

        if "fundamentals" in data and isinstance(data["fundamentals"], dict):
            for key, value in data["fundamentals"].items():
                if value == 0:
                    data["fundamentals"][key] = None

        data["ohlcv"] = cleaned_ohlcv

        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)

        return {"status": "success", "rows_cleaned": len(cleaned_ohlcv)}

    # ---- document mode ------------------------------------------------

    def _clean_document(self, symbol: str) -> Dict[str, Any]:
        """Clean parsed document IR blocks and flatten to plain text for chunker.py."""
        trans_dir = TRANS_DOCUMENTS / symbol
        cleaned_dir = CLEANED_DOCUMENTS / symbol
        cleaned_dir.mkdir(parents=True, exist_ok=True)

        if not trans_dir.exists():
            logger.warning(f"[cleaner] [{symbol}] no parsed input found at {trans_dir}")
            return {"status": "no_data", "files_cleaned": 0}

        files_cleaned = 0
        for file_path in trans_dir.iterdir():
            if file_path.is_file() and file_path.suffix == ".json":
                self._clean_json_file(file_path, cleaned_dir)
                files_cleaned += 1

        if files_cleaned == 0:
            logger.warning(f"[cleaner] [{symbol}] no JSON files found in {trans_dir}")
            return {"status": "no_data", "files_cleaned": 0}

        return {"status": "success", "files_cleaned": files_cleaned}

    def _clean_json_file(self, file_path: Path, output_dir: Path) -> None:
        """Clean a single parsed-IR-blocks JSON file and write it out as plain text."""
        with open(file_path, 'r') as f:
            ir_blocks = json.load(f)

        cleaned_blocks = self.clean_ir_blocks(ir_blocks)
        text = self.render_blocks_to_text(cleaned_blocks)

        output_file = output_dir / f"{file_path.stem}.txt"
        with open(output_file, 'w') as f:
            f.write(text)

    def render_blocks_to_text(self, blocks: List[Dict[str, Any]]) -> str:
        """
        Flatten cleaned IR blocks to plain text, but keep enough Markdown
        structure alive for chunker.py's MarkdownHeaderTextSplitter to do
        anything useful:
          - header blocks get their '#'*level prefix back (this used to be
            dropped, which meant every cleaned .txt file was one headerless
            blob — chunker.py importing MarkdownHeaderTextSplitter had
            nothing to split on).
          - list items get a leading '- '.
          - paragraphs and tables (already Markdown from parser.py) pass
            through as-is.
        """
        lines = []
        for block in blocks:
            content = block.get('content', '')
            if not (isinstance(content, str) and content.strip()):
                continue

            block_type = block.get('type', 'paragraph')
            stripped = content.strip()

            if block_type == 'header':
                level = block.get('hierarchical_level', 1) or 1
                level = max(1, min(6, level))
                lines.append(f"{'#' * level} {stripped}")
            elif block_type == 'list_item':
                lines.append(f"- {stripped}")
            else:
                lines.append(stripped)

        return "\n\n".join(lines)

    def clean_ir_blocks(self, ir_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Apply the complete cleaning workflow to IR blocks:
        1. Page-aware grouping
        2. Dynamic frequency analysis for headers/footers
        3. Static denylist filtering (literal + regex)
        4. Execution with stripping and normalization

        Args:
            ir_blocks: List of IR blocks from parser

        Returns:
            Cleaned list of IR blocks
        """
        page_groups = self._group_by_page(ir_blocks)
        dynamic_deletion_set = self._detect_dynamic_deletion_candidates(page_groups)
        static_deletion_set = self._build_static_deletion_set()
        regex_patterns = self._static_regex_patterns()
        combined_deletion_set = dynamic_deletion_set.union(static_deletion_set)

        cleaned_blocks = []
        for block in ir_blocks:
            content = block.get('content')
            if isinstance(content, str):
                stripped = content.strip()
                if stripped in combined_deletion_set:
                    continue
                if any(pattern.fullmatch(stripped) for pattern in regex_patterns):
                    continue

            cleaned_block = self._normalize_block(block)
            cleaned_blocks.append(cleaned_block)

        return cleaned_blocks

    def _group_by_page(self, ir_blocks: List[Dict[str, Any]]) -> Dict[int, List[Dict[str, Any]]]:
        """Group all text blocks by their page_number attribute."""
        page_groups = {}
        for block in ir_blocks:
            page_num = block.get('page_number', 1)
            if page_num not in page_groups:
                page_groups[page_num] = []
            page_groups[page_num].append(block)
        return page_groups

    def _detect_dynamic_deletion_candidates(self, page_groups: Dict[int, List[Dict[str, Any]]]) -> Set[str]:
        """Detect and tag headers, footers, and page-numbered text using frequency analysis."""
        short_blocks = []
        for page_num, blocks in page_groups.items():
            for block in blocks:
                if (block.get('type') in ['paragraph', 'header'] and
                        isinstance(block.get('content'), str) and
                        len(block['content']) < 80):
                    short_blocks.append(block)

        string_page_count = Counter()
        string_to_pages: Dict[str, Set[int]] = {}

        for block in short_blocks:
            content = block.get('content', '').strip()
            if content:
                string_page_count[content] += 1
                string_to_pages.setdefault(content, set()).add(block.get('page_number', 1))

        deletion_set = set()
        threshold = 3  # minimum number of distinct pages for being flagged

        for text, page_set in string_to_pages.items():
            if len(page_set) >= threshold:
                deletion_set.add(text)

        logger.info(f"Detected {len(deletion_set)} dynamic deletion candidates")
        return deletion_set

    def _build_static_deletion_set(self) -> Set[str]:
        """Literal (non-regex) denylist entries — matched via exact block-content equality."""
        return {p for p in self.DENYLIST_PATTERNS if not self._is_regex_pattern(p)}

    def _static_regex_patterns(self) -> List[re.Pattern]:
        """Regex denylist entries, compiled once, matched separately via fullmatch()."""
        return [re.compile(p) for p in self.DENYLIST_PATTERNS if self._is_regex_pattern(p)]

    @staticmethod
    def _is_regex_pattern(pattern: str) -> bool:
        return bool(re.search(r'[.*+?^${}()|[\]\\]', pattern))

    def _normalize_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize text content in a block, preserving table structures."""
        normalized_block = block.copy()

        if (isinstance(normalized_block.get('content'), str) and
                normalized_block.get('type') != 'table'):
            content = normalized_block['content']
            normalized_content = re.sub(r'\s+', ' ', content).strip()
            normalized_block['content'] = normalized_content

        return normalized_block

    def _is_valid_date_format(self, date_str: str) -> bool:
        """Validate that a date string parses as YYYY-MM-DD."""
        if not isinstance(date_str, str):
            return False
        try:
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
                return False
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
