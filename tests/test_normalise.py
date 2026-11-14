from decimal import Decimal
import pytest
from app.sources.normalise import normalise


def test_normalise(raw):
    row = normalise(raw)
    assert row["source_job_id"] == "123"
    assert row["latitude"] == Decimal("-37.8136")
    assert row["salary_min"] == 0
    assert row["salary_currency"] == "AUD"
    assert row["employment_type"] == "full_time / permanent"
    assert row["posted_at"].utcoffset().total_seconds() == 0
    assert row["raw_payload"] == raw


def test_optional_fields():
    row = normalise({"id": 5, "title": "Cleaner"})
    assert row["salary_min"] is None
    assert row["company_name"] is None
    assert row["source_job_id"] == "5"


@pytest.mark.parametrize("changes", [{"id": None}, {"title": ""}, {"salary_min": "NaN"}, {"created": "invalid"}])
def test_invalid(raw, changes):
    with pytest.raises(ValueError):
        normalise(raw | changes)
