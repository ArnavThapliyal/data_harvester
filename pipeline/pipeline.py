#!/usr/bin/env python3
"""
Pipeline orchestration logic.

PipelineRunner does exactly three things, nothing else:
    1. Run the appropriate stage modules, in order, for each symbol.
    2. Log every stage start/end, every symbol, every status.
    3. Validate the metadata dict each stage's run() call returns.

It has zero knowledge of *how* a stage does its job — that logic lives in the
stage's own module. If a comment in this file ever explains *how* a stage
does its job, that comment is wrong and belongs in that stage's module
instead.

ACTIVE CHAIN (STAGE_ORDER):
    document_crawler -> index

    Down from seven stages to two. type_router, parser, cleaner, chunker,
    and embedder used to each be an independent stage writing its own
    directory for the next one to read — data/transient/, data/cleaned/,
    data/chunked/, data/embedded/. All of that is gone. pipeline/indexer.py
    now does route -> parse -> clean -> chunk -> embed -> upsert as one
    in-memory call per file; the intermediate directories only existed to
    hand data between process boundaries that no longer exist. See
    indexer.py's module docstring for why this also makes each file's
    indexing atomic without any explicit rollback machinery.

    document_crawler stays a separate stage deliberately — it's slow,
    network-bound, and rate-limited against BSE/NSE/screener.in. You want
    to be able to re-run indexing (e.g. after tuning chunk_size or
    switching embedding models) without re-hitting those sites.

    Normalizer is intentionally excluded from STAGE_ORDER this pass —
    [DEFERRED], not removed.

    Numeric collection/cleaning is intentionally excluded this pass —
    [DEFERRED], not removed.

FAILURE MODEL:
    Symbol-level: document_crawler failing for a symbol skips index for
    that symbol (nothing to index yet) and marks the symbol failed. Within
    index, failure is per FILE — indexer.py's index_symbol() already
    isolates one bad file from the rest of the symbol's files (see its
    docstring); a symbol only gets marked failed here if the index stage
    itself raises, which happens when index_symbol()'s own bookkeeping
    breaks, not when an individual document fails to parse (that's
    files_failed in the returned metadata, still a "success" status for
    the symbol as a whole if at least one file made it in).

METADATA CONTRACT: [CONFIRM]
    Each stage's run(symbol) is expected to eventually return a dict shaped
    roughly like {"status": "success" | "skipped" | "no_data", ...}. That
    contract isn't locked in against the real stage modules yet, so
    _normalize_stage_result() tolerates a stage returning None or something
    non-dict rather than crashing on it.

TAG LEGEND:
    [MISSING]  - functionality not implemented yet, flagged rather than faked
    [DEFERRED] - module exists, intentionally not in the active chain this pass
    [CONFIRM]  - verify against the real module's interface once finalized
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from pipeline.Retrieval.Document.document_crawler import run as run_document_crawler
from pipeline.indexer import Indexer
from pipeline.normalizer import Normalizer  # instantiated, not wired into STAGE_ORDER — [DEFERRED]

logger = logging.getLogger(__name__)

# Single source of truth for stage names. main.py imports this directly for
# --stage's argparse choices, so the CLI and the runner can never drift into
# two different stage taxonomies again.
STAGE_ORDER = [
    "document_crawler",
    "index",
]


class PipelineRunner:

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

        self._indexer = Indexer()
        self._normalizer = Normalizer()  # [DEFERRED] instantiated, not called from run()

        self._stage_fns: Dict[str, Callable[[str], Any]] = {
            "document_crawler": self._call_document_crawler,
            "index": self._call_index,
        }

    # ---- stage adapters -----------------------------------------------

    def _call_document_crawler(self, symbol: str) -> Any:
        return run_document_crawler(symbol)

    def _call_index(self, symbol: str) -> Any:
        return self._indexer.index_symbol(symbol)

    # ---- core run loop --------------------------------------------------

    def run(self, symbols: List[str], stage: Optional[str] = None) -> Dict[str, Any]:
        if stage is not None and stage not in STAGE_ORDER:
            raise ValueError(f"Unknown stage {stage!r}. Must be one of {STAGE_ORDER}")

        stages_to_run = [stage] if stage else list(STAGE_ORDER)
        logger.info(f"Starting pipeline for {len(symbols)} symbol(s) — stages: {stages_to_run}")

        succeeded: List[str] = []
        failed: List[str] = []

        for symbol in symbols:
            logger.info(f"[Pipeline] [{symbol}] starting")
            symbol_failed = False

            for stage_name in stages_to_run:
                logger.info(f"[{stage_name}] [{symbol}] starting")
                try:
                    raw_result = self._stage_fns[stage_name](symbol)
                    metadata = self._normalize_stage_result(raw_result)
                    self._validate_metadata(stage_name, symbol, metadata)
                    logger.info(f"[{stage_name}] [{symbol}] completed: {metadata}")
                except Exception as exc:
                    logger.error(f"[{stage_name}] [{symbol}] failed: {exc}", exc_info=True)
                    symbol_failed = True
                    break  # downstream stages depend on this one's output — no point continuing

            if symbol_failed:
                logger.error(f"[Pipeline] [{symbol}] aborted — see failed stage above")
                failed.append(symbol)
            else:
                logger.info(f"[Pipeline] [{symbol}] completed successfully")
                succeeded.append(symbol)

        logger.info(
            f"Pipeline run complete: {len(succeeded)} succeeded, "
            f"{len(failed)} failed, out of {len(symbols)}"
        )
        return {"total": len(symbols), "succeeded": succeeded, "failed": failed}

    # ---- metadata handling ------------------------------------------------

    @staticmethod
    def _normalize_stage_result(raw: Any) -> Dict[str, Any]:
        if raw is None:
            # [CONFIRM] stage returned nothing — assumed success since no exception was raised.
            return {"status": "success"}
        if isinstance(raw, dict):
            return raw
        # [CONFIRM] stage returned a non-dict — wrapping rather than dropping it.
        return {"status": "success", "raw_result": raw}

    @staticmethod
    def _validate_metadata(stage_name: str, symbol: str, metadata: Dict[str, Any]) -> None:
        """[CONFIRM] Minimal shape check until each stage's real return contract is locked in."""
        if "status" not in metadata:
            logger.warning(f"[{stage_name}] [{symbol}] metadata missing 'status' key: {metadata}")
        elif metadata["status"] not in ("success", "skipped", "no_data"):
            logger.warning(f"[{stage_name}] [{symbol}] unexpected status value: {metadata['status']!r}")
