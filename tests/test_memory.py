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


def test_save_memory_result_lists_other_existing_keys(temp_memory_file):
    memory.save_memory("location", "Hisar")

    result = memory.save_memory("hometown", "Chandigarh")

    assert "Saved: hometown = Chandigarh" in result
    assert "Other saved keys: location" in result


def test_save_memory_result_omits_key_list_when_no_other_keys(temp_memory_file):
    result = memory.save_memory("location", "Hisar")

    assert result == "Saved: location = Hisar"
    assert "Other saved keys" not in result


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


def test_search_memory_falls_back_to_all_facts_when_nothing_matches(temp_memory_file):
    memory.save_memory("location", "Hisar")

    # Deliberate behavior: no match at all falls back to the full
    # fact list, so the model can reason over what's available rather
    # than get nothing back.
    assert memory.search_memory("nonexistent") == "location: Hisar"


def test_search_memory_matches_via_token_overlap_not_just_substring(temp_memory_file):
    memory.save_memory("location", "Hisar, Haryana")

    # "hisar city" is not a literal substring of "location: Hisar, Haryana",
    # but "hisar" overlaps as a whole word/token.
    assert memory.search_memory("hisar city") == "location: Hisar, Haryana"


def test_search_memory_ranks_stronger_matches_first(temp_memory_file):
    memory.save_memory("location", "Hisar, Haryana, India")
    memory.save_memory("note", "Hisar is a nice place")

    result = memory.search_memory("location hisar")

    assert result.splitlines()[0] == "location: Hisar, Haryana, India"


def test_search_memory_handles_corrupted_json_gracefully(temp_memory_file):
    temp_memory_file.write_text("not valid json{{{")

    assert memory.search_memory("anything") == ""
