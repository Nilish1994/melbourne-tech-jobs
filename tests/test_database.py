from contextlib import contextmanager
from unittest.mock import Mock
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func, text
from app.db.session import connection
from app.main import app
from app.models.job import jobs
from app.services.ingestion import upsert_jobs, ingest
from app.services.quota import DatabaseQuota, QuotaExceeded
from app.sources.normalise import normalise


def test_duplicate_update_preserves_identity(conn, raw):
    row = normalise(raw)
    assert upsert_jobs(conn, [row, row]) == 1
    before = conn.execute(select(jobs).where(jobs.c.source_job_id == "123")).mappings().one()
    upsert_jobs(conn, [normalise(raw | {"title": "Senior Developer"})])
    after = conn.execute(select(jobs).where(jobs.c.source_job_id == "123")).mappings().one()
    assert after["id"] == before["id"]
    assert after["first_seen_at"] == before["first_seen_at"]
    assert after["last_seen_at"] >= before["last_seen_at"]
    assert after["title"] == "Senior Developer"
    assert after["raw_payload"]["title"] == "Senior Developer"
    assert conn.scalar(select(func.count()).select_from(jobs)) == 1


def test_api(conn, raw):
    upsert_jobs(conn, [normalise(raw), normalise(raw | {"id": "456", "title": "Nurse", "description": "Hospital", "location": {"display_name": "Geelong"}})])
    app.dependency_overrides[connection] = lambda: conn
    try:
        with TestClient(app) as client:
            result = client.get("/jobs?search=developer&location=Melbourne").json()
            assert result["total"] == 1
            assert "raw_payload" not in result["items"][0]
            job_id = result["items"][0]["id"]
            assert client.get(f"/jobs/{job_id}").status_code == 200
            assert client.get(f"/jobs/{uuid.uuid4()}").status_code == 404
            assert client.get("/jobs/bad-uuid").status_code == 422
            assert client.get("/jobs?page_size=101").status_code == 422
            assert client.get("/jobs?search=%25").json()["total"] == 0
            first = client.get("/jobs?page_size=1&page=1").json()
            second = client.get("/jobs?page_size=1&page=2").json()
            assert first["items"][0]["id"] != second["items"][0]["id"]
            assert client.get("/health").status_code == 200
    finally:
        app.dependency_overrides.clear()


class TransactionEngine:
    def __init__(self, conn):
        self.conn = conn
    @contextmanager
    def begin(self):
        with self.conn.begin_nested():
            yield self.conn


@pytest.mark.parametrize("number, age", [(250, "2 hours"), (1000, "2 days"), (2500, "10 days")])
def test_quota_persists_and_blocks(conn, number, age):
    conn.execute(text("INSERT INTO adzuna_requests SELECT clock_timestamp() - cast(:age AS interval) FROM generate_series(1, :number)"), {"age": age, "number": number})
    with pytest.raises(QuotaExceeded):
        DatabaseQuota(TransactionEngine(conn)).acquire()


def test_quota_reservation(conn):
    DatabaseQuota(TransactionEngine(conn)).acquire()
    assert conn.scalar(text("SELECT count(*) FROM adzuna_requests")) == 1


def test_bad_page_is_atomic(conn, raw):
    client = Mock()
    client.pages.return_value = [[raw, {"id": "bad"}]]
    with pytest.raises(ValueError):
        ingest(TransactionEngine(conn), client, "Melbourne", 1)
    assert conn.scalar(select(func.count()).select_from(jobs)) == 0
