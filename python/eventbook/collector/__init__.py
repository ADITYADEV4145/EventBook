"""Local-only dataset ingestion. No network or order-submission code lives here."""

from .local_ingest import ingest_jsonl

__all__ = ["ingest_jsonl"]
