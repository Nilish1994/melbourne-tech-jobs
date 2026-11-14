import uuid
from sqlalchemy import (MetaData, Table, Column, Text, Numeric, DateTime, Boolean,
                        UniqueConstraint, Index, func)
from sqlalchemy.dialects.postgresql import UUID, JSONB

metadata = MetaData()
jobs = Table(
    "jobs", metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
    Column("source", Text, nullable=False),
    Column("source_job_id", Text, nullable=False),
    Column("title", Text, nullable=False),
    Column("company_name", Text), Column("location", Text),
    Column("latitude", Numeric(10, 7)), Column("longitude", Numeric(10, 7)),
    Column("description", Text), Column("salary_min", Numeric(14, 2)),
    Column("salary_max", Numeric(14, 2)), Column("salary_currency", Text),
    Column("employment_type", Text), Column("category", Text),
    Column("source_url", Text), Column("posted_at", DateTime(timezone=True)),
    Column("first_seen_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("last_seen_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    Column("raw_payload", JSONB, nullable=False),
    UniqueConstraint("source", "source_job_id", name="uq_jobs_source_job"),
)
Index("ix_jobs_first_seen_id", jobs.c.first_seen_at.desc(), jobs.c.id.desc())
# Trigram indexes for substring search are installed by the migration.
