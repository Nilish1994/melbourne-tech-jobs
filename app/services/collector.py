"""Tracked collection; only successful runs advance the age-filter checkpoint."""
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import math
import uuid
from sqlalchemy import select, update, insert, func, text, case
from sqlalchemy.exc import SQLAlchemyError
from app.models.ingestion_run import ingestion_runs as runs
from app.services.ingestion import upsert_jobs
from app.services.quota import QuotaExceeded
from app.sources.adzuna import AdzunaError, validate_category
from app.sources.normalise import normalise

COLLECTOR_LOCK = 73410922  # Separate from the existing quota reservation lock.


class AlreadyRunning(RuntimeError):
    pass


class CollectionInterrupted(Exception):
    pass


@dataclass(frozen=True)
class CollectionOptions:
    location: str = "Melbourne"
    category: str | None = "it-jobs"
    max_pages: int = 2
    incremental: bool = False
    lookback_days: int = 7
    overlap_days: int = 2

    def __post_init__(self):
        if not self.location.strip() or len(self.location) > 200:
            raise ValueError("location must contain 1–200 characters")
        validate_category(self.category)
        if not 1 <= self.max_pages <= 250:
            raise ValueError("max-pages must be between 1 and 250")
        if not 1 <= self.lookback_days <= 3650 or not 0 <= self.overlap_days <= 3650:
            raise ValueError("lookback must be 1–3650 days and overlap 0–3650 days")


def incremental_days(now, checkpoint, lookback_days, overlap_days):
    # Round OUT to whole provider days; do not discard overlap results locally.
    anchor = min(now - timedelta(days=lookback_days), checkpoint or now)
    cutoff = anchor - timedelta(days=overlap_days)
    return max(1, math.ceil((now - cutoff).total_seconds() / 86400))


@contextmanager
def collector_lock(engine):
    # Session lock covers every location and both manual and scheduled CLI runs.
    # Invalidating on exit closes the physical session even after DB errors.
    with engine.connect() as conn:
        try:
            if not conn.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": COLLECTOR_LOCK}):
                raise AlreadyRunning("An Adzuna collector is already running; no API calls made")
            conn.commit()
            yield conn
        finally:
            conn.invalidate()


class LockedTransactions:
    """Use the lock-owning session for all audit and page transactions."""
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def begin(self):
        # Never reconnect silently after losing the session-level lock.
        if self.conn.invalidated:
            raise RuntimeError("Collector database session lost")
        with self.conn.begin():
            yield self.conn


def run_collection(engine, client_factory, options):
    with collector_lock(engine) as conn:
        return collect(LockedTransactions(conn), client_factory, options)


def safe_error(exc):
    # Fixed summaries: never persist exception strings, payloads or request URLs.
    if isinstance(exc, QuotaExceeded):
        return "Adzuna quota exhausted; wait for the rolling quota window"
    if isinstance(exc, AdzunaError):
        return exc.safe_summary()
    if isinstance(exc, (CollectionInterrupted, KeyboardInterrupt)):
        return "Collection interrupted; previously committed pages retained"
    if isinstance(exc, SQLAlchemyError):
        return "Database operation failed; previously committed pages retained"
    return "Collection failed during configuration or source processing"


def collect(transactions, client_factory, options, now=None):
    """Internal implementation. Production caller must hold collector_lock."""
    now = now or datetime.now(timezone.utc)
    location = " ".join(options.location.split())
    run_id = uuid.uuid4()
    with transactions.begin() as conn:
        # Holding the exclusive session lock proves prior running rows are orphaned.
        conn.execute(update(runs).where(runs.c.source == "adzuna", runs.c.status == "running")
                     .values(status=case((runs.c.pages_completed > 0, "partial"), else_="failed"),
                             finished_at=now, error_summary="Previous collector ended without finalising; recovered under exclusive lock"))
        checkpoint = conn.scalar(select(func.max(runs.c.started_at)).where(
            runs.c.source == "adzuna", func.lower(runs.c.search_location) == location.lower(),
            runs.c.search_category.is_not_distinct_from(options.category),
            runs.c.status == "success"))
        days = incremental_days(now, checkpoint, options.lookback_days, options.overlap_days) if options.incremental else None
        conn.execute(insert(runs).values(
            id=run_id, source="adzuna", search_location=location,
            search_category=options.category, started_at=now,
            status="running", mode="incremental" if options.incremental else "full",
            max_pages=options.max_pages, lookback_days=options.lookback_days,
            overlap_days=options.overlap_days, max_days_old=days,
            pages_requested=0, pages_completed=0, observations_processed=0,
            newly_inserted_jobs=0, existing_jobs_updated=0))
    status, error = "partial", "Page budget reached; search window may contain more jobs"
    try:
        client = client_factory()  # Credential/config failures are tracked as runs too.
        for page_number in range(1, options.max_pages + 1):
            with transactions.begin() as conn:
                conn.execute(update(runs).where(runs.c.id == run_id)
                             .values(pages_requested=runs.c.pages_requested + 1))
            page = client.fetch_page(location, page_number, max_days_old=days,
                                     category=options.category)
            records = [normalise(raw) for raw in page]
            with transactions.begin() as conn:
                counts = upsert_jobs(conn, records, detailed=True)
                # Job changes and progress counters commit together or roll back together.
                conn.execute(update(runs).where(runs.c.id == run_id).values(
                    pages_completed=runs.c.pages_completed + 1,
                    observations_processed=runs.c.observations_processed + len(records),
                    newly_inserted_jobs=runs.c.newly_inserted_jobs + counts.inserted,
                    existing_jobs_updated=runs.c.existing_jobs_updated + counts.updated))
            if len(page) < 50:
                status, error = "success", None
                break
    except (Exception, KeyboardInterrupt) as exc:
        error = safe_error(exc)
        with transactions.begin() as conn:
            completed = conn.scalar(select(runs.c.pages_completed).where(runs.c.id == run_id))
        status = "quota_exhausted" if isinstance(exc, QuotaExceeded) else ("partial" if completed else "failed")
    with transactions.begin() as conn:
        conn.execute(update(runs).where(runs.c.id == run_id).values(
            status=status, error_summary=error, finished_at=func.clock_timestamp()))
        return dict(conn.execute(select(runs).where(runs.c.id == run_id)).mappings().one())
