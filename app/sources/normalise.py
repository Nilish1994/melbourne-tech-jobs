from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation


def normalise(raw: dict) -> dict:
    source_id = raw.get("id")
    if isinstance(source_id, bool) or not isinstance(source_id, (str, int)) or not str(source_id).strip():
        raise ValueError("Adzuna job has no valid id")
    if not isinstance(raw.get("title"), str) or not raw["title"].strip():
        raise ValueError("Adzuna job has no title")

    def nested(key, field):
        value = raw.get(key)
        return value.get(field) if isinstance(value, dict) else None

    def number(key):
        value = raw.get(key)
        if value is None:
            return None
        try:
            parsed = Decimal(str(value))
            if not parsed.is_finite():
                raise ValueError("Non-finite number")
            return parsed
        except (InvalidOperation, ValueError):
            raise ValueError(f"Invalid {key}") from None

    posted = None
    if raw.get("created"):
        posted = datetime.fromisoformat(raw["created"].replace("Z", "+00:00"))
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
    return dict(source="adzuna", source_job_id=str(source_id), title=raw["title"].strip(),
                company_name=nested("company", "display_name"), location=nested("location", "display_name"),
                latitude=number("latitude"), longitude=number("longitude"),
                description=raw.get("description"), salary_min=number("salary_min"),
                salary_max=number("salary_max"), salary_currency="AUD",
                employment_type=" / ".join(filter(None, [raw.get("contract_time"), raw.get("contract_type")])) or None,
                category=nested("category", "label"), source_url=raw.get("redirect_url"),
                posted_at=posted, is_active=True, raw_payload=raw)
