import json
from io import BytesIO

import agent.reference_image as reference_image_module
from agent.reference_image import find_reference_image_url


class FakeResponse:
    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_find_reference_image_url_returns_best_match(monkeypatch):
    payload = {
        "query": {
            "pages": {
                "123": {
                    "imageinfo": [{"url": "https://upload.wikimedia.org/example.jpg"}]
                }
            }
        }
    }

    monkeypatch.setattr(
        reference_image_module.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(payload),
    )

    url = find_reference_image_url("Antikythera mechanism")

    assert url == "https://upload.wikimedia.org/example.jpg"


def test_find_reference_image_url_returns_none_when_no_pages(monkeypatch):
    payload = {"query": {"pages": {}}}

    monkeypatch.setattr(
        reference_image_module.urllib.request,
        "urlopen",
        lambda *args, **kwargs: FakeResponse(payload),
    )

    assert find_reference_image_url("something obscure") is None
