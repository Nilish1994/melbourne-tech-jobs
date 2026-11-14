import os
import pytest
from app.db.session import get_engine


@pytest.fixture
def engine():
    if os.environ.get("TEST_DATABASE") != "1" or os.environ.get("POSTGRES_DB") != "melbourne_jobs_test":
        pytest.fail("Database tests require the isolated Compose tests service")
    return get_engine()


@pytest.fixture
def conn(engine):
    with engine.connect() as connection:
        transaction = connection.begin()
        yield connection
        transaction.rollback()


@pytest.fixture
def raw():
    return {"id": "123", "title": "Developer", "company": {"display_name": "Example"},
            "location": {"display_name": "Melbourne, Victoria"}, "latitude": -37.8136,
            "longitude": 144.9631, "description": "Build software", "salary_min": 0,
            "salary_max": 120000, "contract_time": "full_time", "contract_type": "permanent",
            "category": {"label": "IT Jobs"}, "created": "2026-09-01T10:00:00Z",
            "redirect_url": "https://www.adzuna.com.au/jobs/details/123"}
