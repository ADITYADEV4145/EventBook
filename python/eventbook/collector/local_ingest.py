"""Validate an account-holder's local capture and create a local research dataset."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import duckdb
import polars as pl

from eventbook.models import Action, BookEvent, Side


@dataclass(frozen=True)
class IngestedDataset:
    dataset_id: str
    event_count: int
    parquet_path: Path
    metadata_path: Path


def ingest_jsonl(input_path: str | Path, data_directory: str | Path = "data") -> IngestedDataset:
    """Convert a local JSONL capture to ignored Parquet and DuckDB metadata files."""
    source_path = Path(input_path)
    raw_bytes = source_path.read_bytes()
    dataset_id = hashlib.sha256(raw_bytes).hexdigest()[:16]
    events = _read_events(raw_bytes)
    _validate_sequences(events)

    root = Path(data_directory)
    processed_directory = root / "processed"
    processed_directory.mkdir(parents=True, exist_ok=True)
    parquet_path = processed_directory / f"{dataset_id}.parquet"
    metadata_path = root / "local_metadata.duckdb"
    _write_parquet(events, parquet_path)
    _write_metadata(metadata_path, dataset_id, parquet_path, len(events))
    return IngestedDataset(dataset_id, len(events), parquet_path, metadata_path)


def _read_events(raw_bytes: bytes) -> list[BookEvent]:
    events = []
    for line_number, line in enumerate(raw_bytes.decode().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            events.append(BookEvent(
                timestamp_ns=row["timestamp_ns"],
                sequence=row["sequence"],
                ticker=row["ticker"],
                side=Side(row["side"]),
                action=Action(row["action"]),
                price_cents=row["price_cents"],
                quantity=row["quantity"],
                order_id=row.get("order_id", ""),
            ))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid local event at line {line_number}") from error
    if not events:
        raise ValueError("local capture contains no events")
    return events


def _validate_sequences(events: list[BookEvent]) -> None:
    previous_by_ticker: dict[str, int] = {}
    for event in events:
        previous = previous_by_ticker.get(event.ticker)
        if previous is not None and event.sequence <= previous:
            raise ValueError(f"non-monotonic sequence for {event.ticker}")
        previous_by_ticker[event.ticker] = event.sequence


def _write_parquet(events: list[BookEvent], path: Path) -> None:
    rows = [{
        "timestamp_ns": event.timestamp_ns,
        "sequence": event.sequence,
        "ticker": event.ticker,
        "side": str(event.side),
        "action": str(event.action),
        "price_cents": event.price_cents,
        "quantity": event.quantity,
        "order_id": event.order_id,
    } for event in events]
    pl.DataFrame(rows).write_parquet(path)


def _write_metadata(path: Path, dataset_id: str, parquet_path: Path, event_count: int) -> None:
    with duckdb.connect(str(path)) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS local_datasets (
                dataset_id VARCHAR PRIMARY KEY,
                parquet_path VARCHAR NOT NULL,
                event_count BIGINT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT current_timestamp
            )
        """)
        connection.execute(
            "INSERT OR REPLACE INTO local_datasets (dataset_id, parquet_path, event_count) VALUES (?, ?, ?)",
            [dataset_id, str(parquet_path), event_count],
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest a local EventBook JSONL capture. No network access is used.")
    parser.add_argument("input", help="Path to an account-holder local JSONL capture")
    parser.add_argument("--data-directory", default="data")
    arguments = parser.parse_args()
    dataset = ingest_jsonl(arguments.input, arguments.data_directory)
    print(json.dumps({"dataset_id": dataset.dataset_id, "event_count": dataset.event_count, "parquet_path": str(dataset.parquet_path)}))


if __name__ == "__main__":
    main()
