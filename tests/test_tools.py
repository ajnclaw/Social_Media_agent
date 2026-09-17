import pytest

from agent.config import SANDBOX_DIR
from agent.tools import is_allowed_api_url, safe_path


def test_allows_https_request_to_known_domain():
    assert is_allowed_api_url("https://api.open-meteo.com/v1/forecast") is True


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
