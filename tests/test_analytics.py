from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.session import connection
from app.main import app
from app.services.ingestion import upsert_jobs
from app.sources.normalise import normalise


def iso(days_ago):
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")


def job(raw, n, *, title, description="", days_ago=1, salary=(None, None), location="Melbourne CBD, Melbourne"):
    return normalise(raw | {
        "id": str(n), "title": title, "description": description, "created": iso(days_ago),
        "salary_min": salary[0], "salary_max": salary[1],
        "company": {"display_name": f"Company {n % 3}"}, "location": {"display_name": location},
    })


@pytest.fixture
def client(conn, raw):
    records = [
        # Current 30-day window: 4 jobs.
        job(raw, 1, title="Python Developer", description="Django, AWS", salary=(120000, 140000)),
        job(raw, 2, title="Senior Python Engineer", description="FastAPI and AWS", days_ago=3,
            salary=(150000, 170000), location="Richmond, Melbourne"),
        job(raw, 3, title="React Developer", description="TypeScript", days_ago=10, salary=(110000, 110000)),
        job(raw, 4, title="Java Developer", days_ago=20, salary=(55, 65)),  # hourly rate: excluded
        # Previous 30-day window: 2 jobs, both React.
        job(raw, 5, title="React Engineer", days_ago=40),
        job(raw, 6, title="Frontend React Developer", days_ago=50, location="Richmond, Melbourne"),
    ]
    upsert_jobs(conn, records)
    app.dependency_overrides[connection] = lambda: conn
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


def test_summary(client):
    body = client.get("/analytics/summary?days=30").json()
    assert body["jobs"] == 4
    assert body["companies"] == 3
    assert body["salary_coverage_pct"] == 75.0  # 3 of 4 have a plausible annual salary
    assert body["jobs_last_7_days"] == 2
    assert body["total_jobs_stored"] == 6
    assert body["top_skill"] == {"skill": "AWS", "jobs": 2}  # ties break alphabetically


def test_skills_share_and_change(client):
    body = client.get("/analytics/skills?days=30").json()
    assert body["total_jobs"] == 4
    by_skill = {item["skill"]: item for item in body["items"]}
    assert by_skill["Python"]["jobs"] == 2
    assert by_skill["Python"]["share_pct"] == 50.0
    assert by_skill["Python"]["group"] == "Languages"
    # React: 1 of 4 now vs 2 of 2 before -> share fell 75 points.
    assert by_skill["React"]["previous_jobs"] == 2
    assert by_skill["React"]["share_change_pts"] == -75.0
    assert body["items"][0]["skill"] in {"AWS", "Python"}


def test_skills_filtered_by_group(client):
    items = client.get("/analytics/skills?group=Cloud%20%26%20DevOps").json()["items"]
    assert [item["skill"] for item in items] == ["AWS"]
    assert client.get("/analytics/skills?group=Nope").status_code == 404


def test_skill_groups(client):
    groups = {g["group"]: g["skills"] for g in client.get("/analytics/skills/groups").json()}
    assert "Python" in groups["Languages"]


def test_trend(client):
    body = client.get("/analytics/skills/trend?skill=Python&skill=React&weeks=12").json()
    assert body["skills"] == ["Python", "React"]
    assert sum(point["total_jobs"] for point in body["points"]) == 6
    assert all(set(point) == {"week", "total_jobs", "Python", "React"} for point in body["points"])
    assert client.get("/analytics/skills/trend?skill=Cobol").status_code == 404
    assert client.get("/analytics/skills/trend").status_code == 422


def test_salaries(client):
    body = client.get("/analytics/salaries?days=30&min_jobs=1").json()
    assert body["overall"]["jobs"] == 3
    assert body["overall"]["median"] == 130000
    python = next(item for item in body["items"] if item["skill"] == "Python")
    assert python["jobs"] == 2
    assert python["median"] == 145000
    assert "Java" not in {item["skill"] for item in body["items"]}  # only an hourly rate
    medians = [item["median"] for item in body["items"]]
    assert medians == sorted(medians, reverse=True)


def test_locations(client):
    body = client.get("/analytics/locations?days=30").json()
    assert body["items"][0] == {"area": "Melbourne CBD", "jobs": 3, "share_pct": 75.0}
    assert body["items"][1]["area"] == "Richmond"


def test_job_list_hides_description_and_filters_by_skill(client):
    body = client.get("/jobs?skill=Python").json()
    assert body["total"] == 2
    item = body["items"][0]
    assert "description" not in item and "raw_payload" not in item
    assert "Python" in item["skills"]
    assert "description" not in client.get(f"/jobs/{item['id']}").json()


@pytest.mark.parametrize("url", ["/analytics/skills?days=1", "/analytics/salaries?limit=0",
                                 "/analytics/locations?days=999", "/analytics/skills/trend?skill=Python&weeks=1"])
def test_parameter_bounds(client, url):
    assert client.get(url).status_code == 422
