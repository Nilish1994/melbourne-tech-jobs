"""Persistent collection audit and incremental checkpoint metadata."""
from sqlalchemy import Table, Column, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.models.job import metadata

ingestion_runs = Table(
    "ingestion_runs", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("source", Text, nullable=False),
    Column("search_location", Text, nullable=False),
    Column("search_category", Text),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("finished_at", DateTime(timezone=True)),
    Column("status", Text, nullable=False),
    Column("mode", Text, nullable=False),
    Column("max_pages", Integer, nullable=False),
    Column("lookback_days", Integer, nullable=False),
    Column("overlap_days", Integer, nullable=False),
    Column("max_days_old", Integer),
    Column("pages_requested", Integer, nullable=False),
    Column("pages_completed", Integer, nullable=False),
    Column("observations_processed", Integer, nullable=False),
    Column("newly_inserted_jobs", Integer, nullable=False),
    Column("existing_jobs_updated", Integer, nullable=False),
    Column("error_summary", Text),
)
