"""Abstract base class for financial data collectors.

Minimal child class example (not runnable):

    class NSECollector(BaseNumericCollector):
        SOURCE_NAME = "NSE"
        BASE_URL = "https://..."
        BATCH_SIZE = 50
        MAX_RETRIES = 3
        OUTPUT_COLUMNS = [...]

        def build_request(self, batch): ...
        def fetch_batch(self, request): ...
        def parse_response(self, response): ...
        def normalize_record(self, record): ...
"""

from __future__ import annotations

import csv
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
_UNIVERSE_CSV = _PACKAGE_ROOT / "config" / "company_universe.csv"
_DEFAULT_OUTPUT_DIR = _PACKAGE_ROOT / "data" / "cleaned"
_SYMBOL_FIELD_ALIASES = ("symbol", "ticker", "Syobol", "syobol")
_COMPANY_NAME_ALIASES = ("company_name", "name")
_EXCHANGE_ALIASES = ("exchange", "series")
_SECTOR_ALIASES = ("sector", "market_cap_category")
_BATCH_DELAY_SECONDS = 1.0
_CHILD_CLASS_ATTRIBUTES = (
    "SOURCE_NAME",
    "BASE_URL",
    "BATCH_SIZE",
    "MAX_RETRIES",
    "OUTPUT_COLUMNS",
)
_RETRY_EXCEPTIONS = (
    TimeoutError,
    ConnectionError,
    httpx.TimeoutException,
    httpx.TransportError,
    httpx.HTTPStatusError,
    httpx.HTTPError,
    OSError,
    ValueError,
    KeyError,
    json.JSONDecodeError,
)


def _validate_child_class_attributes(cls: type) -> None:
    missing = [name for name in _CHILD_CLASS_ATTRIBUTES if not hasattr(cls, name)]
    if missing:
        raise TypeError(
            f"{cls.__name__} must define class attributes: {', '.join(missing)}"
        )


def _extract_symbol(row: dict[str, str]) -> str:
    for field in _SYMBOL_FIELD_ALIASES:
        value = (row.get(field) or "").strip()
        if value:
            return value.upper()
    return ""


def _normalize_universe_row(row: dict[str, str], symbol: str) -> dict[str, str]:
    company_name = ""
    for field in _COMPANY_NAME_ALIASES:
        if row.get(field):
            company_name = str(row[field]).strip()
            break

    exchange = ""
    for field in _EXCHANGE_ALIASES:
        if row.get(field):
            exchange = str(row[field]).strip()
            break

    sector = ""
    for field in _SECTOR_ALIASES:
        if row.get(field):
            sector = str(row[field]).strip()
            break

    return {
        "symbol": symbol,
        "company_name": company_name,
        "exchange": exchange,
        "isin": str(row.get("isin", "")).strip(),
        "sector": sector,
        "industry": str(row.get("industry", "")).strip(),
    }


def _record_symbol(record: dict) -> str:
    for key in ("symbol", "ticker"):
        value = record.get(key)
        if value:
            return str(value).strip().upper()
    return ""


def _export_path(
    output_dir: Path,
    source_name: str,
    extension: str,
    compress_exports: bool,
) -> Path:
    date_stamp = datetime.now(UTC).strftime("%Y%m%d")
    if extension == "csv":
        suffix = ".csv.gz" if compress_exports else ".csv"
    else:
        suffix = f".{extension}"
    filename = f"{source_name.lower()}_{date_stamp}{suffix}"
    return output_dir / source_name.lower() / filename


def _verify_export(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"export file was not created: {path}")


def _log_export_summary(
    logger: logging.Logger,
    source_name: str,
    path: Path,
    df: pd.DataFrame,
    export_format: str,
) -> None:
    metadata = {
        "source": source_name,
        "format": export_format,
        "path": str(path),
        "row_count": len(df),
        "columns": list(df.columns),
        "timestamp": datetime.now(UTC).isoformat(),
        "size_bytes": os.path.getsize(path),
    }
    logger.info("export summary: %s", json.dumps(metadata, default=str))


class BaseNumericCollector(ABC):
    """Abstract parent for all financial data collectors."""

    SOURCE_NAME: str
    BASE_URL: str
    BATCH_SIZE: int
    MAX_RETRIES: int
    OUTPUT_COLUMNS: list[str]

    def __init__(
        self,
        universe_csv: Path | str | None = None,
        output_dir: Path | str | None = None,
        export_mode: str = "overwrite",
        compress_exports: bool = False,
        logger: logging.Logger | None = None,
    ) -> None:
        _validate_child_class_attributes(self.__class__)

        self.universe_csv = Path(universe_csv or _UNIVERSE_CSV)
        self.output_dir = Path(output_dir or _DEFAULT_OUTPUT_DIR)
        self.export_mode = export_mode
        self.compress_exports = compress_exports
        self.logger = logger or logging.getLogger(self.__class__.__name__)

        self.symbols: list[str] = []
        self.batches: list[list[str]] = []
        self.failed_symbols: list[str] = []
        self.failure_log: list[dict[str, Any]] = []
        self.collected_symbols: list[str] = []
        self.missing_symbols: list[str] = []
        self.raw_records: list[dict[str, Any]] = []
        self.output_df: pd.DataFrame = pd.DataFrame()

        self.total_requests: int = 0
        self.total_failures: int = 0
        self.last_successful_run_timestamp: datetime | None = None
        self.api_downtime_events: list[dict[str, Any]] = []

        self._symbol_rows: dict[str, dict[str, str]] = {}
        self._batch_responses: list[Any] = []

    @abstractmethod
    def build_request(self, batch: list[str]) -> Any:
        """Returns a fully constructed request object/dict for a batch of symbols."""

    @abstractmethod
    def fetch_batch(self, request: Any) -> Any:
        """Sends the request; returns raw response."""

    @abstractmethod
    def parse_response(self, response: Any) -> list[dict]:
        """Parses raw response into a list of raw record dicts."""

    @abstractmethod
    def normalize_record(self, record: dict) -> dict:
        """Maps one raw record dict into the internal standard format."""

    def run(self) -> None:
        """Top-level pipeline orchestrator."""
        self.symbols = []
        self.batches = []
        self.failed_symbols = []
        self.failure_log = []
        self.collected_symbols = []
        self.missing_symbols = []
        self.raw_records = []
        self.output_df = pd.DataFrame()
        self.total_requests = 0
        self.total_failures = 0
        self.api_downtime_events = []
        self._symbol_rows = {}
        self._batch_responses = []

        self.read_symbols()
        for batch in self.batches:
            response = self.execute_batch(batch)
            if response is not None:
                self._batch_responses.append(response)
            time.sleep(_BATCH_DELAY_SECONDS)

        self.raw_records = self.collect_results(self._batch_responses)
        normalized = self.normalize_dataset(self.raw_records)
        self.output_df = self.clean_dataset(normalized)

        for column in self.output_df.select_dtypes(include="number").columns:
            negatives = self.output_df[column] < 0
            if negatives.any():
                self.logger.warning(
                    "negative values in column %s (%d row(s))",
                    column,
                    int(negatives.sum()),
                )

        if list(self.output_df.columns) != list(self.OUTPUT_COLUMNS):
            raise ValueError(
                f"schema mismatch: expected {self.OUTPUT_COLUMNS}, "
                f"got {list(self.output_df.columns)}"
            )

        self.export_csv(self.output_df)
        self.export_parquet(self.output_df)
        self.last_successful_run_timestamp = datetime.now(UTC)
        self.logger.info(
            "run complete | source=%s | symbols=%d | collected=%d | "
            "missing=%d | failed=%d | requests=%d | failures=%d | "
            "downtime_events=%d | last_success=%s",
            self.SOURCE_NAME,
            len(self.symbols),
            len(self.collected_symbols),
            len(self.missing_symbols),
            len(self.failed_symbols),
            self.total_requests,
            self.total_failures,
            len(self.api_downtime_events),
            self.last_successful_run_timestamp.isoformat(),
        )

    def read_symbols(self) -> list[str]:
        """Read company universe CSV and return deduplicated symbol list."""
        if not self.universe_csv.exists():
            raise FileNotFoundError(f"universe CSV not found: {self.universe_csv}")

        symbols: list[str] = []
        seen: set[str] = set()
        self._symbol_rows = {}

        with self.universe_csv.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                symbol = _extract_symbol(row)
                if not symbol:
                    continue
                if symbol in seen:
                    continue
                seen.add(symbol)
                self._symbol_rows[symbol] = _normalize_universe_row(row, symbol)
                symbols.append(symbol)

        self.symbols = symbols
        self.batches = self.create_batches(self.symbols)
        return self.symbols

    def create_batches(self, symbols: list[str]) -> list[list[str]]:
        """Split symbol list into chunks of size BATCH_SIZE."""
        batch_size = int(self.BATCH_SIZE)
        if batch_size < 1:
            raise ValueError("BATCH_SIZE must be at least 1")
        return [
            symbols[index : index + batch_size]
            for index in range(0, len(symbols), batch_size)
        ]

    def execute_batch(self, batch: list[str]) -> Any:
        """Build request, fetch batch, retry on failure, or record failure."""
        started = time.perf_counter()
        self.total_requests += 1
        try:
            request = self.build_request(batch)
            response = self.fetch_batch(request)
            status_code = getattr(response, "status_code", None)
            self.logger.debug(
                "batch response | status=%s | elapsed=%.3fs",
                status_code,
                time.perf_counter() - started,
            )
            return response
        except _RETRY_EXCEPTIONS as exc:
            self.logger.warning(
                "batch request failed (will retry) | symbols=%s | error=%s",
                batch,
                exc,
            )
            try:
                response = self.retry_request(batch, attempt=1)
                status_code = getattr(response, "status_code", None)
                self.logger.debug(
                    "batch response after retry | status=%s | elapsed=%.3fs",
                    status_code,
                    time.perf_counter() - started,
                )
                return response
            except Exception as retry_exc:
                self.handle_failure(batch, retry_exc)
                self.total_failures += 1
                self.api_downtime_events.append(
                    {
                        "symbols": list(batch),
                        "error_type": type(retry_exc).__name__,
                        "error_message": str(retry_exc),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                return None

    def retry_request(self, batch: list[str], attempt: int) -> Any:
        """Retry full batch flow with exponential backoff up to MAX_RETRIES."""
        max_retries = int(self.MAX_RETRIES)
        last_error: Exception | None = None

        while attempt <= max_retries:
            time.sleep(min(2**attempt, 60))
            self.total_requests += 1
            try:
                request = self.build_request(batch)
                return self.fetch_batch(request)
            except _RETRY_EXCEPTIONS as exc:
                last_error = exc
                self.logger.warning(
                    "retry %d/%d failed | symbols=%s | error=%s",
                    attempt,
                    max_retries,
                    batch,
                    exc,
                )
                attempt += 1

        if last_error is not None:
            raise last_error
        raise RuntimeError("retry_request exhausted without capturing an error")

    def handle_failure(self, batch: list[str], error: Exception) -> None:
        """Record failed symbols and log failure details."""
        for symbol in batch:
            if symbol not in self.failed_symbols:
                self.failed_symbols.append(symbol)

        self.failure_log.append(
            {
                "symbols": list(batch),
                "error_type": type(error).__name__,
                "error_message": str(error),
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )
        self.logger.error(
            "batch collection failed | symbols=%s | error_type=%s | error=%s",
            batch,
            type(error).__name__,
            error,
        )

    def collect_results(self, responses: list[Any]) -> list[dict]:
        """Parse successful responses and merge into one raw dataset."""
        combined: list[dict] = []
        collected_set: set[str] = set()

        for response in responses:
            if response is None:
                continue
            for record in self.parse_response(response):
                combined.append(record)
                symbol = _record_symbol(record)
                if symbol:
                    collected_set.add(symbol)

        self.collected_symbols = sorted(collected_set)
        self.missing_symbols = sorted(
            symbol for symbol in self.symbols if symbol not in collected_set
        )
        if self.missing_symbols:
            self.logger.warning(
                "missing data for %d symbol(s): %s",
                len(self.missing_symbols),
                ", ".join(self.missing_symbols[:20]),
            )

        return combined

    def normalize_dataset(self, raw_records: list[dict]) -> list[dict]:
        """Apply normalize_record to each raw record."""
        return [self.normalize_record(record) for record in raw_records]

    def clean_dataset(self, records: list[dict]) -> pd.DataFrame:
        """Clean, validate, and shape records into the export schema."""
        if not records:
            return pd.DataFrame(columns=self.OUTPUT_COLUMNS)

        df = pd.DataFrame(records)

        if "symbol" in df.columns:
            df["symbol"] = (
                df["symbol"]
                .astype(str)
                .str.strip()
                .str.upper()
                .replace({"": pd.NA})
            )
        if "exchange" in df.columns:
            df["exchange"] = df["exchange"].astype(str).str.strip().str.upper()
        if "currency" in df.columns:
            df["currency"] = df["currency"].astype(str).str.strip().str.upper()

        for column in df.columns:
            if column.endswith("_date") or column in {"date", "timestamp"}:
                df[column] = pd.to_datetime(df[column], errors="coerce")
            elif df[column].dtype == object:
                numeric = pd.to_numeric(df[column], errors="coerce")
                if numeric.notna().any() and df[column].notna().any():
                    non_null = df[column].notna()
                    if numeric[non_null].notna().all():
                        df[column] = numeric

        df = df.dropna(how="all")
        if "symbol" in df.columns:
            df = df.dropna(subset=["symbol"])
            df = df.drop_duplicates(subset=["symbol"], keep="first")

        missing_required = [
            col
            for col in self.OUTPUT_COLUMNS
            if col not in df.columns or df[col].isna().all()
        ]
        if missing_required:
            self.logger.error(
                "missing or empty required fields: %s",
                ", ".join(missing_required),
            )
            raise ValueError(
                f"missing required fields for schema: {missing_required}"
            )

        for column in self.OUTPUT_COLUMNS:
            if column not in df.columns:
                df[column] = pd.NA

        return df[self.OUTPUT_COLUMNS]

    def export_csv(self, df: pd.DataFrame) -> None:
        """Write cleaned dataset to CSV with export metadata."""
        path = _export_path(
            self.output_dir,
            self.SOURCE_NAME,
            "csv",
            self.compress_exports,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not (self.export_mode == "append" and path.exists())
        df.to_csv(
            path,
            index=False,
            mode="a" if self.export_mode == "append" else "w",
            header=write_header,
            compression="gzip" if self.compress_exports else None,
        )
        _verify_export(path)
        _log_export_summary(self.logger, self.SOURCE_NAME, path, df, "csv")

    def export_parquet(self, df: pd.DataFrame) -> None:
        """Write cleaned dataset to Parquet with export metadata."""
        path = _export_path(
            self.output_dir,
            self.SOURCE_NAME,
            "parquet",
            self.compress_exports,
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.export_mode == "append" and path.exists():
            existing = pd.read_parquet(path)
            df = pd.concat([existing, df], ignore_index=True)
        df.to_parquet(
            path,
            index=False,
            compression="gzip" if self.compress_exports else None,
        )
        _verify_export(path)
        _log_export_summary(self.logger, self.SOURCE_NAME, path, df, "parquet")
