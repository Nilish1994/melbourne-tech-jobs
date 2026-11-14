import pytest
from fastapi.testclient import TestClient

from app.db.session import connection
from app.main import app
from app.services.ingestion import upsert_jobs
from app.sources.normalise import normalise


@pytest.fixture
def client(conn, raw):
    records = [normalise(raw | {"id": str(n), "title": f"Python Developer {n}", "description": f"Django role {n}"})
               for n in range(5)]
    records.append(normalise(raw | {"id": "demo-1", "title": "Demo"}) | {"source": "demo"})
    upsert_jobs(conn, records)
    app.dependency_overrides[connection] = lambda: conn
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_feed_includes_descriptions_and_skills_but_not_demo(client):
    body = client.get("/feed/jobs").json()
    assert len(body["items"]) == 5
    assert body["has_more"] is False
    item = body["items"][0]
    assert item["description"].startswith("Django role")
    assert item["skills"] == ["Django", "Python"]
    assert "raw_payload" not in item
    assert all(i["title"] != "Demo" for i in body["items"])


def test_feed_pages_with_cursor_without_gaps_or_repeats(client):
    seen, params = [], {"limit": 2}
    while True:
        body = client.get("/feed/jobs", params=params).json()
        seen += [item["id"] for item in body["items"]]
        if not body["has_more"]:
            break
        params = {"limit": 2, "since": body["next_cursor"]["since"], "after_id": body["next_cursor"]["after_id"]}
    assert len(seen) == len(set(seen)) == 5


def test_feed_after_latest_cursor_is_empty(client):
    body = client.get("/feed/jobs?limit=500").json()
    cursor = body["next_cursor"]
    after = client.get("/feed/jobs", params={"since": cursor["since"], "after_id": cursor["after_id"]}).json()
    assert after == {"items": [], "has_more": False, "next_cursor": None}
