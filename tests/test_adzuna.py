from unittest.mock import Mock
import httpx
import pytest
from app.sources.adzuna import AdzunaClient, AdzunaError, retry_delay


def make_client(handler):
    quota, sleep = Mock(), Mock()
    client = AdzunaClient("secret-id", "secret-key", quota,
                          httpx.Client(transport=httpx.MockTransport(handler)), sleep)
    return client, quota, sleep


def test_pagination_and_query():
    requests = []
    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"results": [{}] * (50 if len(requests) == 1 else 1)})
    client, quota, _ = make_client(handler)
    assert len(list(client.pages("Melbourne", 4))) == 2
    assert requests[1].url.path.endswith("/au/search/2")
    assert requests[0].url.params["where"] == "Melbourne, Victoria, Australia"
    assert "what" not in requests[0].url.params
    assert "category" not in requests[0].url.params
    assert quota.acquire.call_count == 2


def test_max_pages():
    client, quota, _ = make_client(lambda _: httpx.Response(200, json={"results": [{}] * 50}))
    assert len(list(client.pages("Melbourne", 2))) == 2
    assert quota.acquire.call_count == 2


@pytest.mark.parametrize("status", [400, 401, 403])
def test_non_retryable_error(status):
    client, quota, sleep = make_client(lambda _: httpx.Response(status))
    with pytest.raises(AdzunaError, match=f"http_status={status}") as error:
        client.fetch_page("Melbourne", 1)
    assert "secret" not in str(error.value)
    assert quota.acquire.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize("status", [429, 500, 503])
def test_retry_then_success(status):
    responses = iter([httpx.Response(status, headers={"Retry-After": "3"}),
                      httpx.Response(200, json={"results": []})])
    client, quota, sleep = make_client(lambda _: next(responses))
    assert client.fetch_page("Melbourne", 1) == []
    sleep.assert_called_once_with(3)
    assert quota.acquire.call_count == 2


def test_exhausted_retries():
    client, quota, _ = make_client(lambda _: httpx.Response(503))
    with pytest.raises(AdzunaError, match="category=http_server_error"):
        client.fetch_page("Melbourne", 1)
    assert quota.acquire.call_count == 4


def test_transport_failure():
    def handler(request):
        raise httpx.ConnectError("secret URL", request=request)
    client, quota, _ = make_client(handler)
    with pytest.raises(AdzunaError, match="category=transport_error"):
        client.fetch_page("Melbourne", 1)
    assert quota.acquire.call_count == 4


@pytest.mark.parametrize("payload", [{}, {"results": None}, {"results": [1]}, []])
def test_bad_payload(payload):
    client, _, _ = make_client(lambda _: httpx.Response(200, json=payload))
    with pytest.raises(AdzunaError, match="category=invalid_payload"):
        client.fetch_page("Melbourne", 1)


def test_bad_json():
    client, _, _ = make_client(lambda _: httpx.Response(200, text="not json"))
    with pytest.raises(AdzunaError):
        client.fetch_page("Melbourne", 1)


def test_long_retry_after_stops():
    client, quota, sleep = make_client(lambda _: httpx.Response(429, headers={"Retry-After": "3600"}))
    with pytest.raises(AdzunaError, match="category=rate_limited"):
        client.fetch_page("Melbourne", 1)
    assert quota.acquire.call_count == 1
    sleep.assert_not_called()


def test_retry_http_date():
    assert retry_delay("Wed, 01 Jan 2020 00:00:00 GMT", 0) == 0


@pytest.mark.parametrize("status, category", [
    (400, "http_client_error"), (401, "http_client_error"),
    (403, "http_client_error"), (410, "http_client_error"),
    (429, "rate_limited"), (500, "http_server_error"),
    (503, "http_server_error"), (302, "unexpected_http_status"),
])
def test_single_attempt_safe_http_diagnostics(status, category):
    client, quota, sleep = make_client(lambda _: httpx.Response(
        status, text="secret-id secret-key https://example.invalid/?app_key=secret-key",
        headers={"Retry-After": "3600", "Location": "https://example.invalid/?app_key=secret-key"}))
    with pytest.raises(AdzunaError) as caught:
        client.fetch_page("Melbourne", 1, max_days_old=9, max_attempts=1)
    error = caught.value
    assert error.http_status == status
    assert error.category == category
    assert str(error) == f"Adzuna error: http_status={status} category={category}"
    assert "secret" not in repr(error)
    assert "https" not in str(error)
    assert quota.acquire.call_count == 1
    sleep.assert_not_called()


def test_single_transport_attempt_and_redaction():
    def handler(request):
        raise httpx.ConnectError(f"secret-key {request.url}", request=request)
    client, quota, sleep = make_client(handler)
    with pytest.raises(AdzunaError) as caught:
        client.fetch_page("Melbourne", 1, max_attempts=1)
    assert caught.value.http_status is None
    assert caught.value.category == "transport_error"
    assert "secret" not in str(caught.value)
    assert quota.acquire.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize("response", [
    httpx.Response(200, text="secret-key invalid json"),
    httpx.Response(200, json={"secret": "secret-key"}),
    httpx.Response(200, json={"results": ["secret-key"]}),
])
def test_invalid_payload_status_and_redaction(response):
    client, quota, sleep = make_client(lambda _: response)
    with pytest.raises(AdzunaError) as caught:
        client.fetch_page("Melbourne", 1, max_attempts=1)
    assert caught.value.http_status == 200
    assert caught.value.category == "invalid_payload"
    assert "secret" not in str(caught.value)
    assert quota.acquire.call_count == 1
    sleep.assert_not_called()


@pytest.mark.parametrize("category, status", [
    ("secret-key", "secret-id"), (["secret-key"], True), (None, 999),
])
def test_error_fields_are_allowlisted(category, status):
    error = AdzunaError(category, status)
    assert error.category == "unknown_error"
    assert error.http_status is None
    assert str(error) == "Adzuna error: http_status=none category=unknown_error"


def test_default_retries_keep_last_http_status():
    client, quota, _ = make_client(lambda _: httpx.Response(503))
    with pytest.raises(AdzunaError) as caught:
        client.fetch_page("Melbourne", 1)
    assert caught.value.http_status == 503
    assert caught.value.category == "http_server_error"
    assert quota.acquire.call_count == 4


def test_single_attempt_valid_payload():
    client, quota, sleep = make_client(lambda _: httpx.Response(200, json={"results": []}))
    assert client.fetch_page("Melbourne", 1, max_days_old=9, max_attempts=1) == []
    assert quota.acquire.call_count == 1
    sleep.assert_not_called()
