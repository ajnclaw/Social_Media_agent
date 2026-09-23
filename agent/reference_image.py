# reference_image.py
#
# Fetches a real reference photo from Wikimedia Commons -- free, no API
# key, well suited for history/mythology subjects (monuments, artifacts,
# classical artwork). Used to ground image generation in a real photo via
# img2img instead of generating a subject purely from imagination.

import json
import urllib.parse
import urllib.request


COMMONS_API = "https://commons.wikimedia.org/w/api.php"


def find_reference_image_url(query):
    """
    Search Wikimedia Commons for an image matching query. Returns the
    full-resolution file URL of the best match, or None if nothing found.
    """
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"filetype:bitmap {query}",
        "gsrnamespace": "6",  # File namespace
        "gsrlimit": "1",
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }

    url = f"{COMMONS_API}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": "ai-agent/1.0"})

    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read())

    pages = data.get("query", {}).get("pages", {})

    for page in pages.values():
        imageinfo = page.get("imageinfo")
        if imageinfo:
            return imageinfo[0]["url"]

    return None


def fetch_reference_image_bytes(query):
    """
    Find and download a reference image for query. Returns raw image
    bytes, or None if no matching image was found on Commons.
    """
    url = find_reference_image_url(query)

    if not url:
        return None

    request = urllib.request.Request(url, headers={"User-Agent": "ai-agent/1.0"})

    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()
