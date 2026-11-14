import random
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import httpx


class AdzunaError(RuntimeError):
    """Only bounded, allowlisted diagnostic data may leave the HTTP client."""
    CATEGORIES = frozenset({
        "configuration_error", "http_client_error", "http_server_error",
        "rate_limited", "unexpected_http_status", "transport_error",
        "invalid_payload", "unknown_error",
    })

    def __init__(self, category, http_status=None):
        self.category = category if isinstance(category, str) and category in self.CATEGORIES else "unknown_error"
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        super().__init__(self.safe_summary())

    def safe_summary(self):
        # Revalidate at the output boundary; never format raw exception arguments.
        category = self.category if isinstance(self.category, str) and self.category in self.CATEGORIES else "unknown_error"
        status = self.http_status if type(self.http_status) is int and 100 <= self.http_status <= 599 else None
        return f"Adzuna error: http_status={status if status is not None else 'none'} category={category}"


CATEGORY_TAG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def validate_category(category):
    """Adzuna category tags are short lowercase slugs such as 'it-jobs'."""
    if category is None:
        return None
    if not isinstance(category, str) or len(category) > 50 or not CATEGORY_TAG.match(category):
        raise ValueError("category must be an Adzuna category tag such as 'it-jobs'")
    return category


def http_error_category(status):
    if status == 429:
        return "rate_limited"
    if 400 <= status < 500:
        return "http_client_error"
    if 500 <= status < 600:
        return "http_server_error"
    return "unexpected_http_status"


def retry_delay(value, attempt):
    if value:
        try:
            return max(0, float(value))
        except ValueError:
            try:
                return max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    return min(30, 2 ** attempt) + random.uniform(0, 1)


class AdzunaClient:
    def __init__(self, app_id, app_key, quota, client, sleep=time.sleep):
        if not app_id or not app_key:
            raise AdzunaError("configuration_error")
        self.app_id, self.app_key = app_id, app_key
        self.quota, self.client, self.sleep = quota, client, sleep

    def fetch_page(self, location, page, max_days_old=None, *, category=None, max_attempts=4):
        if type(max_attempts) is not int or not 1 <= max_attempts <= 4:
            raise ValueError("max_attempts must be between 1 and 4")
        category = validate_category(category)
        params = dict(app_id=self.app_id, app_key=self.app_key,
                      where=f"{location}, Victoria, Australia", results_per_page=50,
                      # sort_by=date is already newest-first; Adzuna now rejects sort_dir=down with HTTP 400.
                      sort_by="date", **{"content-type": "application/json"})
        if max_days_old is not None:
            if not isinstance(max_days_old, int) or max_days_old < 1:
                raise ValueError("max_days_old must be a positive integer")
            params["max_days_old"] = max_days_old
        if category is not None:
            params["category"] = category
        for attempt in range(max_attempts):
            self.quota.acquire()
            try:
                response = self.client.get(f"https://api.adzuna.com/v1/api/jobs/au/search/{page}", params=params)
            except httpx.TransportError:
                if attempt == max_attempts - 1:
                    raise AdzunaError("transport_error") from None
                self.sleep(retry_delay(None, attempt))
                continue
            if response.status_code == 429 or 500 <= response.status_code < 600:
                if attempt == max_attempts - 1:
                    raise AdzunaError(http_error_category(response.status_code), response.status_code)
                delay = retry_delay(response.headers.get("Retry-After"), attempt)
                if delay > 300:
                    raise AdzunaError(http_error_category(response.status_code), response.status_code)
                self.sleep(delay)
                continue
            if response.status_code != 200:
                # Never include request URLs or bodies: credentials are query parameters.
                raise AdzunaError(http_error_category(response.status_code), response.status_code)
            try:
                payload = response.json()
                results = payload["results"]
                if not isinstance(results, list) or not all(isinstance(row, dict) for row in results):
                    raise ValueError()
                return results
            except (ValueError, KeyError, TypeError):
                raise AdzunaError("invalid_payload", response.status_code) from None

    def pages(self, location, max_pages, category=None):
        for page in range(1, max_pages + 1):
            results = self.fetch_page(location, page, category=category)
            if not results:
                break
            yield results
            if len(results) < 50:
                break
