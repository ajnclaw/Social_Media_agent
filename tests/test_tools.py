import pytest

from agent.config import SANDBOX_DIR
from agent.tools import (
    build_request_url,
    is_allowed_api_url,
    safe_path,
    TOOL_PREVIEW_BUILDERS,
)


def test_allows_https_request_to_known_domain():
    assert is_allowed_api_url("https://api.open-meteo.com/v1/forecast") is True


def test_allows_https_request_to_geolocation_domain():
    assert is_allowed_api_url("https://ipapi.co/json/") is True


def test_allows_https_request_to_geocoding_domain():
    assert is_allowed_api_url("https://geocoding-api.open-meteo.com/v1/search") is True


def test_rejects_unknown_domain():
    assert is_allowed_api_url("https://evil.example.com/steal") is False


def test_rejects_non_https_scheme():
    assert is_allowed_api_url("http://api.open-meteo.com/v1/forecast") is False


def test_rejects_domain_confusion_attempt():
    # A hostname that merely *contains* an allowed domain as a substring
    # (not as its actual host) must still be rejected.
    assert is_allowed_api_url("https://api.open-meteo.com.evil.com/") is False


def test_safe_path_allows_paths_inside_sandbox():
    target = safe_path("notes/todo.txt")

    assert target == (SANDBOX_DIR / "notes" / "todo.txt").resolve()


def test_safe_path_blocks_parent_directory_traversal():
    with pytest.raises(PermissionError):
        safe_path("../outside.txt")


def test_safe_path_blocks_absolute_path_escape():
    with pytest.raises(PermissionError):
        safe_path("/etc/passwd")


def test_build_request_url_returns_bare_url_when_no_params():
    url = "https://api.open-meteo.com/v1/forecast"

    assert build_request_url(url) == url


def test_build_request_url_appends_params_with_question_mark():
    url = build_request_url(
        "https://api.frankfurter.app/latest",
        {"from": "USD", "to": "EUR"},
    )

    assert url == "https://api.frankfurter.app/latest?from=USD&to=EUR"


def test_build_request_url_appends_params_with_ampersand_when_query_exists():
    url = build_request_url(
        "https://api.open-meteo.com/v1/forecast?latitude=51.5",
        {"longitude": "-0.12"},
    )

    assert url == "https://api.open-meteo.com/v1/forecast?latitude=51.5&longitude=-0.12"


def test_call_api_preview_shows_the_exact_url_that_will_be_sent():
    preview = TOOL_PREVIEW_BUILDERS["call_api"](
        {"url": "https://api.frankfurter.app/latest", "params": {"from": "USD", "to": "EUR"}}
    )

    assert "https://api.frankfurter.app/latest?from=USD&to=EUR" in preview
