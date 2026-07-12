#!/usr/bin/env python3
"""
Entry point for the data harvester pipeline.

Exactly three supported invocations — nothing else:

    main.py --all-symbols                  # every symbol, every stage
    main.py --symbol SYM                   # one symbol, every stage
    main.py --symbol SYM --stage STAGE     # one symbol, exactly one stage

--stage is only valid alongside --symbol; there is no "all symbols, one
stage" mode in this pass. Add it deliberately later if you need it — don't
let it appear as an accidental side effect of argparse defaults.

Symbol source of truth: config/company_urls.json (produced by
scripts/url_discovery.py). A symbol must have an entry there before it can
be processed — that's what --all-symbols enumerates, and what --symbol is
validated against.
"""

import sys
import json
import time
import logging
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional

from config.settings import COMPANY_URLS_JSON
from pipeline.pipeline import PipelineRunner, STAGE_ORDER

logger = logging.getLogger(__name__)


def setup_logging() -> None:
    """
    Configure the ROOT logger once, in one place.

    Every module's `logging.getLogger(__name__)` — main.py, pipeline.py, and
    every stage module — propagates up to root by default, so attaching
    handlers here (via basicConfig) is enough for all of them. The previous
    version attached handlers to logging.getLogger("__main__") specifically,
    which pipeline.py's logger never propagated into — its INFO-level logs
    were silently going nowhere.
    """
    Path("data").mkdir(exist_ok=True)

    log_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
    log_formatter.converter = time.gmtime  # UTC timestamps

    file_handler = logging.FileHandler("data/pipeline.log")
    file_handler.setFormatter(log_formatter)

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(log_formatter)

    logging.basicConfig(level=logging.INFO, handlers=[file_handler, stdout_handler])


def load_known_symbols() -> List[str]:
    """Every symbol with a discovered-URL entry in company_urls.json."""
    if not COMPANY_URLS_JSON.exists():
        print(f"Error: {COMPANY_URLS_JSON} not found. Run scripts/url_discovery.py first.")
        sys.exit(1)
    try:
        with open(COMPANY_URLS_JSON, "r") as f:
            company_urls = json.load(f)
    except Exception as e:
        print(f"Error reading {COMPANY_URLS_JSON}: {e}")
        sys.exit(1)
    return list(company_urls.keys())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Data Harvester Pipeline",
        epilog=(
            "examples:\n"
            "  %(prog)s --all-symbols\n"
            "  %(prog)s --symbol RELIANCE\n"
            "  %(prog)s --symbol RELIANCE --stage index\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--all-symbols",
        action="store_true",
        help="Process every symbol in company_urls.json, running all stages.",
    )
    selection.add_argument(
        "--symbol",
        type=str,
        metavar="SYM",
        help="Process a single symbol.",
    )

    parser.add_argument(
        "--stage",
        type=str,
        choices=STAGE_ORDER,
        default=None,
        metavar="STAGE",
        help=f"Run exactly one stage instead of the full chain. Requires --symbol. "
             f"One of: {', '.join(STAGE_ORDER)}.",
    )

    args = parser.parse_args()

    if args.stage and args.all_symbols:
        parser.error("--stage can only be combined with --symbol, not --all-symbols.")

    return args


def print_summary(summary: Dict[str, Any]) -> None:
    print(
        f"\n{summary['total']} symbol(s) processed: "
        f"{len(summary['succeeded'])} succeeded, {len(summary['failed'])} failed."
    )
    if summary["failed"]:
        print("Failed: " + ", ".join(summary["failed"]))


def main() -> None:
    setup_logging()
    args = parse_args()

    known_symbols = load_known_symbols()

    if args.all_symbols:
        symbols = known_symbols
        stage: Optional[str] = None
        logger.info(f"Mode: all symbols, all stages ({len(symbols)} symbols)")
    else:
        if args.symbol not in known_symbols:
            print(f"Error: '{args.symbol}' not found in {COMPANY_URLS_JSON}. "
                  f"Run scripts/url_discovery.py or check the symbol spelling.")
            sys.exit(1)
        symbols = [args.symbol]
        stage = args.stage
        if stage:
            logger.info(f"Mode: single symbol, single stage ({args.symbol} / {stage})")
        else:
            logger.info(f"Mode: single symbol, all stages ({args.symbol})")

    runner = PipelineRunner()

    try:
        summary = runner.run(symbols, stage=stage)
    except KeyboardInterrupt:
        logger.info("Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Pipeline failed to start: {e}", exc_info=True)
        sys.exit(1)

    print_summary(summary)
    sys.exit(0 if not summary["failed"] else 1)


if __name__ == "__main__":
    main()
