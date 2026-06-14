"""Async collector for Indian Stock API historical price data."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from collectors.base_numeric_collector import BaseNumericCollector

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_RAW_DIR = _PACKAGE_ROOT / "data" / "raw"
_ENDPOINT = "historical_data"
_PERIOD = "max"
_FILTER = "price"
_RATE_LIMIT_SECONDS = 3.0
_API_KEY_ENV_VARS = ("INDIAN_API_KEY", "INDIA_API_KEY")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _safe_symbol_filename(symbol: str) -> str:
    return re.sub(r"[^\w.-]", "_", symbol.strip().upper())


class IndiaAPICollector(BaseNumericCollector):
    """Fetch per-symbol historical price data and persist raw JSON responses."""

    SOURCE_NAME = "indiaapi"
    BASE_URL = "https://stock.indianapi.in"
    BATCH_SIZE = 1
    MAX_RETRIES = 3
    OUTPUT_COLUMNS = ["symbol", "status_code", "fetched_at"]

    def __init__(
        self,
        *,
        raw_dir: Path | str | None = None,
        overwrite: bool = False,
        rate_limit_seconds: float = _RATE_LIMIT_SECONDS,
        api_key: str | None = None,
        universe_csv: Path | str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(universe_csv=universe_csv, logger=logger)
        self.raw_dir = Path(raw_dir or _DEFAULT_RAW_DIR)
        self.overwrite = overwrite
        self.rate_limit_seconds = rate_limit_seconds
        self.api_key = api_key or self._load_api_key()
        self.started_at: str | None = None
        self.completed_at: str | None = None
        self._run_successful = 0
        self._run_failed = 0
        self._run_skipped = 0

    @staticmethod
    def _load_api_key() -> str:
        for env_name in _API_KEY_ENV_VARS:
            value = os.environ.get(env_name, "").strip()
            if value:
                return value
        names = ", ".join(_API_KEY_ENV_VARS)
        raise ValueError(f"API key not set; export one of: {names}")

    def build_request(self, batch: list[str]) -> dict[str, Any]:
        symbol = batch[0]
        return {
            "method": "GET",
            "url": f"{self.BASE_URL}/{_ENDPOINT}",
            "params": {
                "stock_name": symbol,
                "period": _PERIOD,
                "filter": _FILTER,
            },
            "headers": {"x-api-key": self.api_key},
        }

    def fetch_batch(self, request: dict[str, Any]) -> Any:
        raise NotImplementedError(
            "IndiaAPICollector uses async HTTP; call run() or run_async() instead."
        )

# Collector writes raw JSON directly.
    def parse_response(self, response: Any) -> list[dict]: # Not used.
        return []
# Collector writes raw JSON directly.
    def normalize_record(self, record: dict) -> dict: # Not used.
        return record
# Collector writes raw JSON directly.

    def run(self) -> None:
        """Synchronous entry point for the async collection pipeline."""
        asyncio.run(self.run_async())

    async def run_async(self, symbols: list[str] | None = None) -> None:
        """Collect historical_data for every universe symbol."""
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        if symbols is None:
            symbols = self.read_symbols()
        total = len(symbols)
        self.started_at = _utc_now_iso()
        self._run_successful = 0
        self._run_failed = 0
        self._run_skipped = 0

        self.logger.info(
            "starting indiaapi collection | symbols=%d | raw_dir=%s | "
            "overwrite=%s | rate_limit=%.1fs",
            total,
            self.raw_dir,
            self.overwrite,
            self.rate_limit_seconds,
        )

        timeout = httpx.Timeout(60.0, connect=15.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for index, symbol in enumerate(symbols, start=1):
                requested = await self._process_symbol(client, symbol, index, total)
                if requested and index < total:
                    await asyncio.sleep(self.rate_limit_seconds)

        self.completed_at = _utc_now_iso()
        manifest = self._build_manifest(symbols)
        manifest_path = self.raw_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2),
            encoding="utf-8",
        )

        self.logger.info(
            "collection complete | total=%d | successful=%d | failed=%d | "
            "skipped=%d | manifest=%s",
            manifest["total_companies"],
            manifest["successful"],
            manifest["failed"],
            self._run_skipped,
            manifest_path,
        )

    async def _process_symbol(
        self,
        client: httpx.AsyncClient,
        symbol: str,
        index: int,
        total: int,
    ) -> bool:
        """Process one symbol. Returns True if an HTTP request was made."""
        output_path = self._symbol_output_path(symbol)
        if output_path.exists() and not self.overwrite:
            self._run_skipped += 1
            self.logger.info("[%d/%d] %s SKIP (exists)", index, total, symbol)
            return False

        request = self.build_request([symbol])
        url = request["url"]
        params = request["params"]
        headers = request["headers"]
        self.logger.info(
            "request | [%d/%d] %s | GET %s | params=%s",
            index,
            total,
            symbol,
            url,
            params,
        )

        fetched_at = _utc_now_iso()
        try:
            response = await client.get(url, params=params, headers=headers)
            self.logger.info(
                "response | [%d/%d] %s | status=%d",
                index,
                total,
                symbol,
                response.status_code,
            )
            payload = self._build_result_payload(
                symbol=symbol,
                fetched_at=fetched_at,
                status_code=response.status_code,
                response=response,
            )
            self._write_json(output_path, payload)

            if self._is_success(payload):
                self._run_successful += 1
                self.logger.info("[%d/%d] %s SUCCESS", index, total, symbol)
            else:
                self._run_failed += 1
                self.failed_symbols.append(symbol)
                self.logger.info(
                    "[%d/%d] %s FAIL %s",
                    index,
                    total,
                    symbol,
                    response.status_code,
                )
            return True
        except httpx.HTTPError as exc:
            self._run_failed += 1
            self.failed_symbols.append(symbol)
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            payload = self._build_error_payload(
                symbol=symbol,
                fetched_at=fetched_at,
                status_code=status_code,
                response=getattr(exc, "response", None),
                error=str(exc),
            )
            self._write_json(output_path, payload)
            code_label = status_code if status_code is not None else "ERROR"
            self.logger.info(
                "[%d/%d] %s FAIL %s",
                index,
                total,
                symbol,
                code_label,
            )
            self.logger.error(
                "request exception | symbol=%s | error=%s",
                symbol,
                exc,
                exc_info=exc,
            )
            return True
        except Exception as exc:
            self._run_failed += 1
            self.failed_symbols.append(symbol)
            payload = self._build_error_payload(
                symbol=symbol,
                fetched_at=fetched_at,
                status_code=None,
                response=None,
                error=str(exc),
            )
            self._write_json(output_path, payload)
            self.logger.info("[%d/%d] %s FAIL ERROR", index, total, symbol)
            self.logger.error(
                "unexpected error | symbol=%s | error=%s",
                symbol,
                exc,
                exc_info=exc,
            )
            return True

    def _symbol_output_path(self, symbol: str) -> Path:
        return self.raw_dir / f"{_safe_symbol_filename(symbol)}.json"

    @staticmethod
    def _write_json(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        tmp_path.replace(path)

    def _build_result_payload(
        self,
        *,
        symbol: str,
        fetched_at: str,
        status_code: int,
        response: httpx.Response,
    ) -> dict[str, Any]:
        body_text = response.text
        parsed_body: Any
        try:
            parsed_body = response.json()
        except json.JSONDecodeError:
            parsed_body = body_text

        payload: dict[str, Any] = {
            "symbol": symbol,
            "endpoint": _ENDPOINT,
            "period": _PERIOD,
            "filter": _FILTER,
            "fetched_at": fetched_at,
            "status_code": status_code,
        }

        if status_code == 200:
            payload["data"] = parsed_body
        else:
            payload["success"] = False
            payload["response_body"] = parsed_body
            if body_text and parsed_body == body_text:
                payload["response_body"] = body_text

        return payload

    def _build_error_payload(
        self,
        *,
        symbol: str,
        fetched_at: str,
        status_code: int | None,
        response: httpx.Response | None,
        error: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "symbol": symbol,
            "endpoint": _ENDPOINT,
            "period": _PERIOD,
            "filter": _FILTER,
            "fetched_at": fetched_at,
            "success": False,
            "error": error,
        }
        if status_code is not None:
            payload["status_code"] = status_code
        if response is not None:
            payload["status_code"] = response.status_code
            try:
                payload["response_body"] = response.json()
            except json.JSONDecodeError:
                payload["response_body"] = response.text
        return payload

    @staticmethod
    def _is_success(payload: dict[str, Any]) -> bool:
        return payload.get("status_code") == 200 and "data" in payload

    def _build_manifest(self, symbols: list[str]) -> dict[str, Any]:
        successful = 0
        failed = 0

        for symbol in symbols:
            path = self._symbol_output_path(symbol)
            if not path.exists():
                failed += 1
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                failed += 1
                continue
            if self._is_success(payload):
                successful += 1
            else:
                failed += 1

        return {
            "total_companies": len(symbols),
            "successful": successful,
            "failed": failed,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect India API historical data.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Re-fetch symbols even when a JSON file already exists.",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=_DEFAULT_RAW_DIR,
        help="Directory for per-symbol JSON files and manifest.json.",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=_RATE_LIMIT_SECONDS,
        help="Seconds to wait between API requests.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N symbols (for testing).",
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    _configure_logging(args.verbose)
    collector = IndiaAPICollector(
        raw_dir=args.raw_dir,
        overwrite=args.overwrite,
        rate_limit_seconds=args.rate_limit,
    )
    symbols = None
    if args.limit is not None:
        symbols = collector.read_symbols()[: args.limit]
    asyncio.run(collector.run_async(symbols=symbols))


if __name__ == "__main__":
    main()
