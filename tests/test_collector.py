from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func, text, insert

from app.db.session import connection
from app.main import app
from app.models.ingestion_run import ingestion_runs as runs
from app.models.job import jobs
from app.services.collector import (collect, CollectionOptions, incremental_days,
                                    collector_lock, AlreadyRunning, CollectionInterrupted)
from app.services.quota import DatabaseQuota, QuotaExceeded
from app.sources.adzuna import AdzunaClient, AdzunaError

NOW = datetime(2026, 9, 7, 3, tzinfo=timezone.utc)


class Transactions:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def begin(self):
        with self.conn.begin_nested():
            yield self.conn


def run(conn, pages, **options):
    client = Mock()
    client.fetch_page.side_effect = pages
    result = collect(Transactions(conn), lambda: client, CollectionOptions(**options), now=NOW)
    return result, client


def add_run(conn, *, location="Melbourne", category="it-jobs", status="success", age=2, completed=1):
    run_id = uuid.uuid4()
    conn.execute(insert(runs).values(
        id=run_id, source="adzuna", search_location=location, search_category=category,
        started_at=NOW - timedelta(days=age),
        finished_at=None if status == "running" else NOW - timedelta(days=age, hours=-1),
        status=status, mode="incremental", max_pages=2, lookback_days=7, overlap_days=2,
        max_days_old=9, pages_requested=completed, pages_completed=completed,
        observations_processed=0, newly_inserted_jobs=0, existing_jobs_updated=0))
    return run_id


def test_incremental_query_and_no_local_overlap_discard(conn, raw):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"results": [raw]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = AdzunaClient("id", "key", Mock(), http)
        result = collect(Transactions(conn), lambda: client, CollectionOptions(incremental=True), now=NOW)
    assert result["max_days_old"] == 9
    assert result["newly_inserted_jobs"] == 1
    assert requests[0].url.params["max_days_old"] == "9"
    assert requests[0].url.params["sort_by"] == "date"
    assert "sort_dir" not in requests[0].url.params  # rejected by Adzuna (HTTP 400)
    assert "what" not in requests[0].url.params
    assert requests[0].url.params["category"] == "it-jobs"
    assert result["search_category"] == "it-jobs"


def test_all_categories_sends_no_category(conn, raw):
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"results": [raw]})
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        client = AdzunaClient("id", "key", Mock(), http)
        result = collect(Transactions(conn), lambda: client, CollectionOptions(category=None), now=NOW)
    assert "category" not in requests[0].url.params
    assert result["search_category"] is None


@pytest.mark.parametrize("category", ["IT Jobs", "it_jobs", "-it", "it--jobs", "x" * 51, ""])
def test_invalid_category_rejected(category):
    with pytest.raises(ValueError):
        CollectionOptions(category=category)


def test_full_mode_omits_age_filter(conn):
    result, client = run(conn, [[]])
    assert result["max_days_old"] is None
    client.fetch_page.assert_called_once_with("Melbourne", 1, max_days_old=None, category="it-jobs")


@pytest.mark.parametrize("checkpoint, expected", [
    (None, 9), (NOW - timedelta(days=1), 9),
    (NOW - timedelta(days=10, seconds=1), 13),
])
def test_overlap_rounding(checkpoint, expected):
    assert incremental_days(NOW, checkpoint, 7, 2) == expected


def test_checkpoint_scoped_to_location_and_success(conn):
    add_run(conn, age=12)
    add_run(conn, status="partial", age=1)
    add_run(conn, location="Geelong", age=30)
    add_run(conn, category=None, age=1)  # a different category never moves this checkpoint
    result, _ = run(conn, [[]], incremental=True, location="  melbourne  ")
    assert result["max_days_old"] == 14


def test_tracking_and_duplicate_statistics(conn, raw):
    first, _ = run(conn, [[raw, raw]])
    old = conn.execute(select(jobs)).mappings().one()
    second, _ = run(conn, [[raw | {"title": "Updated title"}]])
    new = conn.execute(select(jobs)).mappings().one()
    assert first["status"] == second["status"] == "success"
    assert first["pages_requested"] == first["pages_completed"] == 1
    assert first["observations_processed"] == 2
    assert first["newly_inserted_jobs"] == 1
    assert first["existing_jobs_updated"] == 0
    assert second["newly_inserted_jobs"] == 0
    assert second["existing_jobs_updated"] == 1
    assert first["finished_at"] is not None
    assert new["id"] == old["id"]
    assert new["first_seen_at"] == old["first_seen_at"]
    assert new["title"] == "Updated title"
    assert conn.scalar(select(func.count()).select_from(runs)) == 2


def test_running_visible_before_fetch(conn):
    def fetch(*args, **kwargs):
        row = conn.execute(select(runs)).mappings().one()
        assert row["status"] == "running"
        assert row["finished_at"] is None
        assert row["pages_requested"] == 1
        return []
    client = Mock(fetch_page=fetch)
    result = collect(Transactions(conn), lambda: client, CollectionOptions(), now=NOW)
    assert result["status"] == "success"


def test_page_budget_is_partial_and_no_checkpoint(conn, raw):
    result, _ = run(conn, [[raw] * 50], max_pages=1, incremental=True)
    assert result["status"] == "partial"
    assert result["observations_processed"] == 50
    assert result["newly_inserted_jobs"] == 1
    assert result["existing_jobs_updated"] == 0
    assert "budget" in result["error_summary"]
    assert conn.scalar(select(func.max(runs.c.started_at)).where(runs.c.status == "success")) is None


@pytest.mark.parametrize("failure, status", [
    (AdzunaError("secret-app-key"), "failed"),
    (QuotaExceeded("secret-app-key"), "quota_exhausted"),
    (CollectionInterrupted(), "failed"),
    (ValueError("secret-app-key"), "failed"),
])
def test_failed_run_without_secrets(conn, failure, status):
    result, _ = run(conn, [failure])
    assert result["status"] == status
    assert result["finished_at"] is not None
    assert result["pages_requested"] == 1
    assert result["pages_completed"] == 0
    assert "secret" not in result["error_summary"]


@pytest.mark.parametrize("error, status", [(AdzunaError("secret"), "partial"),
                                          (QuotaExceeded("secret"), "quota_exhausted")])
def test_prior_pages_retained(conn, raw, error, status):
    result, _ = run(conn, [[raw] * 50, error])
    assert result["status"] == status
    assert result["pages_requested"] == 2
    assert result["pages_completed"] == 1
    assert result["newly_inserted_jobs"] == 1
    assert conn.scalar(select(func.count()).select_from(jobs)) == 1


def test_page_database_failure_rolls_back_jobs_and_counts(conn, raw):
    # Valid normalisation, but the second record exceeds the database salary precision.
    result, _ = run(conn, [[raw, raw | {"id": "456", "salary_min": 10**20}]])
    assert result["status"] == "failed"
    assert result["pages_completed"] == result["newly_inserted_jobs"] == 0
    assert conn.scalar(select(func.count()).select_from(jobs)) == 0


def test_credential_failure_is_tracked(conn):
    def factory():
        raise AdzunaError("credentials must never be stored")
    result = collect(Transactions(conn), factory, CollectionOptions(), now=NOW)
    assert result["status"] == "failed"
    assert result["pages_requested"] == 0


def test_orphan_recovery(conn):
    orphan = add_run(conn, status="running", age=1)
    run(conn, [[]])
    recovered = conn.execute(select(runs).where(runs.c.id == orphan)).mappings().one()
    assert recovered["status"] == "partial"
    assert recovered["finished_at"] is not None
    assert "exclusive lock" in recovered["error_summary"]


def test_scheduler_and_manual_overlap_prevented(engine):
    # Real PostgreSQL sessions, no mocks: a second process cannot own the lock.
    with collector_lock(engine):
        with pytest.raises(AlreadyRunning):
            with collector_lock(engine):
                pytest.fail("overlapping collection was allowed")
    # Closing the owner session releases it for the next run.
    with collector_lock(engine):
        pass


def test_retries_use_persistent_quota(conn, raw):
    responses = iter([httpx.Response(429, headers={"Retry-After": "0"}),
                      httpx.Response(200, json={"results": [raw]})])
    quota = DatabaseQuota(Transactions(conn))
    with httpx.Client(transport=httpx.MockTransport(lambda _: next(responses))) as http:
        client = AdzunaClient("id", "key", quota, http, sleep=lambda _: None)
        result = collect(Transactions(conn), lambda: client, CollectionOptions(), now=NOW)
    assert result["status"] == "success"
    assert result["pages_requested"] == 1
    assert conn.scalar(text("SELECT count(*) FROM adzuna_requests")) == 2


def test_persistent_quota_exhaustion_no_http(conn):
    conn.execute(text("INSERT INTO adzuna_requests SELECT clock_timestamp() - interval '2 hours' FROM generate_series(1,250)"))
    http = Mock()
    client = AdzunaClient("id", "key", DatabaseQuota(Transactions(conn)), http)
    result = collect(Transactions(conn), lambda: client, CollectionOptions(), now=NOW)
    assert result["status"] == "quota_exhausted"
    http.get.assert_not_called()
    assert conn.scalar(text("SELECT count(*) FROM adzuna_requests")) == 250


def test_run_endpoints_and_stats(conn, raw):
    app.dependency_overrides[connection] = lambda: conn
    try:
        with TestClient(app) as client:
            assert client.get("/stats").json()["latest_successful_ingestion_at"] is None
            result, _ = run(conn, [[raw]])
            listing = client.get("/ingestion-runs?page_size=1").json()
            assert listing["total"] == 1
            assert listing["items"][0]["id"] == str(result["id"])
            assert client.get(f"/ingestion-runs/{result['id']}").json()["status"] == "success"
            assert client.get(f"/ingestion-runs/{uuid.uuid4()}").status_code == 404
            assert client.get("/ingestion-runs/bad-id").status_code == 422
            assert client.get("/ingestion-runs?page=0").status_code == 422
            stats = client.get("/stats").json()
            assert stats["stored_job_count"] == 1
            assert stats["source_counts"] == [{"source": "adzuna", "count": 1}]
            assert stats["category_counts"] == [{"category": "IT Jobs", "count": 1}]
            assert stats["latest_successful_ingestion_at"] is not None
    finally:
        app.dependency_overrides.clear()


def test_overlap_skips_before_client_construction(engine):
    from app.services.collector import run_collection
    factory = Mock()
    with collector_lock(engine):
        with pytest.raises(AlreadyRunning):
            run_collection(engine, factory, CollectionOptions())
    factory.assert_not_called()


def test_lost_lock_session_does_not_reconnect(engine):
    from app.services.collector import LockedTransactions
    with collector_lock(engine) as conn:
        transactions = LockedTransactions(conn)
        conn.invalidate()
        with pytest.raises(RuntimeError, match="session lost"):
            with transactions.begin():
                pytest.fail("must not reconnect without lock")


@pytest.mark.parametrize("status, exit_code", [("success", 0), ("partial", 2),
                                               ("quota_exhausted", 3), ("failed", 1)])
def test_cli_reports_counts_and_status(monkeypatch, capsys, status, exit_code):
    from app.cli import ingest as cli
    monkeypatch.setattr(cli, "get_settings", Mock())
    monkeypatch.setattr(cli, "get_engine", Mock())
    runner = Mock(return_value={"id": uuid.uuid4(), "status": status,
        "pages_completed": 1, "pages_requested": 2, "observations_processed": 50,
        "newly_inserted_jobs": 30, "existing_jobs_updated": 20, "error_summary": None})
    monkeypatch.setattr(cli, "run_collection", runner)
    assert cli.main(["--incremental", "--lookback-days", "10", "--overlap-days", "3"]) == exit_code
    output = capsys.readouterr().out
    assert "new 30; updated 20" in output
    options = runner.call_args.args[2]
    assert options.incremental and options.lookback_days == 10 and options.overlap_days == 3


def test_cli_lock_conflict_exit(monkeypatch):
    from app.cli import ingest as cli
    monkeypatch.setattr(cli, "get_settings", Mock())
    monkeypatch.setattr(cli, "get_engine", Mock())
    monkeypatch.setattr(cli, "run_collection", Mock(side_effect=AlreadyRunning("Already running")))
    assert cli.main([]) == 75


@pytest.mark.parametrize("status, category", [
    (400, "http_client_error"), (429, "rate_limited"),
    (503, "http_server_error"), (200, "invalid_payload"),
    (None, "transport_error"),
])
def test_structured_error_persisted_and_printed(conn, monkeypatch, capsys, status, category):
    from app.cli import ingest as cli
    error = AdzunaError(category, status)
    # Even a raw exception message introduced elsewhere must not reach outputs.
    error.args = ("secret-id secret-key https://example.invalid/?app_key=secret-key",)
    result, _ = run(conn, [error])
    expected = f"Adzuna error: http_status={status if status is not None else 'none'} category={category}"
    stored = conn.scalar(select(runs.c.error_summary).where(runs.c.id == result["id"]))
    assert stored == expected
    monkeypatch.setattr(cli, "get_settings", Mock())
    monkeypatch.setattr(cli, "get_engine", Mock())
    monkeypatch.setattr(cli, "run_collection", Mock(return_value=result))
    assert cli.main([]) == 1
    output = capsys.readouterr()
    assert output.err.strip() == expected
    assert "secret" not in output.out + output.err
    assert "https" not in output.out + output.err
