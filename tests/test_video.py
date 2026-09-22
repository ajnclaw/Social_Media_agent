import pytest

import agent.video as video_module
from agent.video import get_audio_duration, split_script_into_slides


def test_split_script_into_slides_splits_on_sentences():
    slides = split_script_into_slides("First sentence. Second sentence.")

    assert slides == ["First sentence", "Second sentence"]


def test_split_script_into_slides_wraps_long_sentences():
    long_sentence = "word " * 40

    slides = split_script_into_slides(long_sentence, max_chars=50)

    assert len(slides) > 1
    assert all(len(slide) <= 50 for slide in slides)


def test_split_script_into_slides_handles_empty_script():
    assert split_script_into_slides("") == [""]


def test_split_script_into_slides_ignores_blank_sentences():
    slides = split_script_into_slides("One sentence.. .Another.")

    assert slides == ["One sentence", "Another"]


def test_split_script_into_slides_splits_long_sentence_on_clause_not_midword():
    sentence = (
        "When an octopus swims, that main heart actually stops beating, "
        "which is part of why they prefer crawling over swimming"
    )

    slides = split_script_into_slides(sentence, max_chars=110)

    assert len(slides) == 2
    assert all(len(slide) <= 110 for slide in slides)
    # Neither chunk should orphan "swimming" from its subject.
    assert slides[-1] != "swimming"
    assert "crawling over swimming" in slides[-1]


def test_get_audio_duration_raises_on_ffprobe_failure(monkeypatch):
    class FakeResult:
        returncode = 1
        stderr = "ffprobe not found"
        stdout = ""

    monkeypatch.setattr(
        video_module.subprocess, "run", lambda *args, **kwargs: FakeResult()
    )

    with pytest.raises(RuntimeError):
        get_audio_duration("narration.mp3")


def test_get_audio_duration_parses_ffprobe_output(monkeypatch):
    class FakeResult:
        returncode = 0
        stderr = ""
        stdout = "12.345\n"

    monkeypatch.setattr(
        video_module.subprocess, "run", lambda *args, **kwargs: FakeResult()
    )

    assert get_audio_duration("narration.mp3") == 12.345
