import json

import pytest

from agent import memory


@pytest.fixture
def temp_memory_file(tmp_path, monkeypatch):
    path = tmp_path / "memory.json"
    monkeypatch.setattr(memory, "MEMORY_FILE", path)
    return path


def test_save_memory_creates_file_with_key_value(temp_memory_file):
    memory.save_memory("location", "Hisar")

    data = json.loads(temp_memory_file.read_text())

    assert data == {"location": "Hisar"}


def test_save_memory_overwrites_existing_key_instead_of_duplicating(temp_memory_file):
    memory.save_memory("location", "Yamunanagar")
    memory.save_memory("location", "Hisar")

    data = json.loads(temp_memory_file.read_text())

    assert data == {"location": "Hisar"}


def test_save_memory_keeps_unrelated_keys(temp_memory_file):
    memory.save_memory("location", "Hisar")
    memory.save_memory("favorite_language", "Python")

    data = json.loads(temp_memory_file.read_text())

    assert data == {"location": "Hisar", "favorite_language": "Python"}


def test_search_memory_matches_on_key(temp_memory_file):
    memory.save_memory("location", "Hisar")

    assert memory.search_memory("location") == "location: Hisar"


def test_search_memory_matches_on_value_case_insensitively(temp_memory_file):
    memory.save_memory("location", "Hisar")

    assert memory.search_memory("HISAR") == "location: Hisar"


def test_search_memory_returns_empty_string_when_no_file(temp_memory_file):
    assert memory.search_memory("anything") == ""


def test_search_memory_returns_empty_string_when_no_match(temp_memory_file):
    memory.save_memory("location", "Hisar")

    assert memory.search_memory("nonexistent") == ""


def test_search_memory_handles_corrupted_json_gracefully(temp_memory_file):
    temp_memory_file.write_text("not valid json{{{")

    assert memory.search_memory("anything") == ""
