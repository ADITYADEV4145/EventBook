import json

import duckdb
import polars as pl
import pytest

from eventbook.collector import ingest_jsonl


def event(sequence: int, quantity: int = 2) -> dict:
    return {"timestamp_ns": sequence, "sequence": sequence, "ticker": "LOCAL", "side": "bid", "action": "add", "price_cents": 50, "quantity": quantity}


def test_local_ingest_writes_parquet_and_duckdb_metadata(tmp_path) -> None:
    source = tmp_path / "capture.jsonl"
    source.write_text("\n".join(json.dumps(event(sequence)) for sequence in (1, 2)))
    dataset = ingest_jsonl(source, tmp_path / "data")
    assert dataset.event_count == 2
    assert pl.read_parquet(dataset.parquet_path).height == 2
    with duckdb.connect(str(dataset.metadata_path), read_only=True) as connection:
        assert connection.execute("SELECT event_count FROM local_datasets").fetchone() == (2,)


def test_local_ingest_rejects_invalid_capture(tmp_path) -> None:
    source = tmp_path / "bad.jsonl"
    source.write_text(json.dumps(event(1, quantity=0)))
    with pytest.raises(ValueError, match="invalid local event"):
        ingest_jsonl(source, tmp_path / "data")
