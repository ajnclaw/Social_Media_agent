# youtube.py
#
# YouTube uploads via the YouTube Data API v3. First call opens a browser
# for a one-time OAuth consent (the account owner logs in and approves);
# the resulting token is cached and silently refreshed after that.

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .config import YOUTUBE_CLIENT_SECRET_PATH, YOUTUBE_TOKEN_PATH


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# "People & Blogs" -- reasonable default category for short narrated content.
DEFAULT_CATEGORY_ID = "22"


def _get_credentials():
    creds = None

    if YOUTUBE_TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(YOUTUBE_TOKEN_PATH), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not YOUTUBE_CLIENT_SECRET_PATH.exists():
                raise FileNotFoundError(
                    f"YouTube OAuth client secret not found: "
                    f"{YOUTUBE_CLIENT_SECRET_PATH}. Download it from Google "
                    f"Cloud Console (APIs & Services > Credentials > "
                    f"OAuth 2.0 Client ID > Desktop app) and save it there."
                )

            flow = InstalledAppFlow.from_client_secrets_file(
                str(YOUTUBE_CLIENT_SECRET_PATH), SCOPES
            )
            creds = flow.run_local_server(port=0)

        YOUTUBE_TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return creds


def upload_video(video_path, title, description, tags=None, privacy_status="private"):
    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags or [],
            "categoryId": DEFAULT_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": privacy_status,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        _, response = request.next_chunk()

    return response
