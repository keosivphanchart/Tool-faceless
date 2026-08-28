"""Instagram Reels via the Meta Graph API's Content Publishing endpoints.

Unlike YouTube/TikTok, Instagram's publish flow doesn't accept a direct
file upload - it fetches the video itself from a URL you give it, so
video_url has to be a publicly reachable address (PUBLIC_BASE_URL +
this app's own GET /media endpoint), not a local file path. Instagram
also only publishes to Business/Creator accounts linked to a Facebook
Page, never a personal account.

One-time setup:
  1. Create an app at https://developers.facebook.com, add the
     "Instagram Graph API" product, and set INSTAGRAM_APP_ID /
     INSTAGRAM_APP_SECRET.
  2. Add INSTAGRAM_REDIRECT_URI as a valid OAuth redirect URI on that
     app, and add a Facebook Page (linked to an Instagram
     Business/Creator account you manage) as a tester/admin.
  3. Set PUBLIC_BASE_URL to this backend's own public HTTPS origin -
     required before publishing works at all, since Meta's servers have
     to be able to fetch the rendered video from it.
  4. Connect the account from the dashboard's Settings page ("Connect
     Instagram") - this walks through Facebook's OAuth consent screen,
     finds the linked Instagram Business Account behind whichever Page
     you authorize, and caches the resulting Page access token + IG user
     id at INSTAGRAM_TOKEN_FILE.

Flow (https://developers.facebook.com/docs/instagram-platform/content-publishing):
  1. authorize(): OAuth code -> short-lived user token -> long-lived user
     token -> GET /me/accounts for the Page's own access token -> GET
     /{page-id}?fields=instagram_business_account for the IG user id.
  2. upload_video(): POST /{ig-user-id}/media (media_type=REELS,
     video_url, caption) -> creation_id, poll GET /{creation_id} until
     status_code=FINISHED, then POST /{ig-user-id}/media_publish.

INSTAGRAM_API_BASE_URL defaults to Meta's real endpoint but is
overridable so this contract can be exercised against a local server in
tests, without needing a live Meta app.
"""
import json
import logging
import time
from pathlib import Path
from urllib.parse import quote

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)

AUTHORIZE_URL = "https://www.facebook.com/v19.0/dialog/oauth"
SCOPES = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"


class InstagramNotConfigured(RuntimeError):
    pass


class InstagramPublishFailed(RuntimeError):
    pass


def _token_path() -> Path:
    return Path(settings.instagram_token_file)


def _require_client_credentials():
    if not settings.instagram_app_id or not settings.instagram_app_secret:
        raise InstagramNotConfigured(
            "Instagram publishing isn't configured yet - set INSTAGRAM_APP_ID / "
            "INSTAGRAM_APP_SECRET (see this module's docstring for setup)."
        )


def _save_token(token: dict) -> None:
    _token_path().parent.mkdir(parents=True, exist_ok=True)
    _token_path().write_text(json.dumps(token), encoding="utf-8")


def _load_token() -> dict | None:
    if not _token_path().exists():
        return None
    return json.loads(_token_path().read_text(encoding="utf-8"))


def is_connected() -> bool:
    return _token_path().is_file()


def disconnect() -> None:
    _token_path().unlink(missing_ok=True)


def build_authorize_url() -> str:
    """Starts the dashboard-driven connect flow: the URL to send the
    browser to for Facebook's consent screen."""
    _require_client_credentials()
    return (
        f"{AUTHORIZE_URL}?client_id={settings.instagram_app_id}&scope={SCOPES}"
        f"&response_type=code&redirect_uri={settings.instagram_redirect_uri}&state=faceless_pipeline"
    )


def complete_authorization(code: str) -> None:
    """Finishes the connect flow: exchanges the code for a long-lived
    Page access token + the linked Instagram Business Account id, and
    caches both at INSTAGRAM_TOKEN_FILE."""
    import requests

    _require_client_credentials()
    base = settings.instagram_api_base_url

    short_lived = requests.get(
        f"{base}/oauth/access_token",
        params={
            "client_id": settings.instagram_app_id,
            "client_secret": settings.instagram_app_secret,
            "redirect_uri": settings.instagram_redirect_uri,
            "code": code,
        },
        timeout=30,
    )
    short_lived.raise_for_status()
    short_lived_token = short_lived.json()["access_token"]

    long_lived = requests.get(
        f"{base}/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": settings.instagram_app_id,
            "client_secret": settings.instagram_app_secret,
            "fb_exchange_token": short_lived_token,
        },
        timeout=30,
    )
    long_lived.raise_for_status()
    user_token = long_lived.json()["access_token"]

    accounts = requests.get(f"{base}/me/accounts", params={"access_token": user_token}, timeout=30)
    accounts.raise_for_status()
    pages = accounts.json().get("data", [])
    if not pages:
        raise InstagramPublishFailed(
            "This Facebook account has no Pages - Instagram publishing needs a Page linked to an "
            "Instagram Business/Creator account."
        )
    page = pages[0]
    page_access_token = page["access_token"]

    page_info = requests.get(
        f"{base}/{page['id']}",
        params={"fields": "instagram_business_account", "access_token": page_access_token},
        timeout=30,
    )
    page_info.raise_for_status()
    ig_account = page_info.json().get("instagram_business_account")
    if not ig_account:
        raise InstagramPublishFailed(
            f"Page '{page.get('name', page['id'])}' has no linked Instagram Business/Creator account."
        )

    _save_token(
        {
            "page_access_token": page_access_token,
            "page_id": page["id"],
            "page_name": page.get("name", ""),
            "ig_user_id": ig_account["id"],
        }
    )
    logger.info("Instagram token cached at %s (IG user %s)", settings.instagram_token_file, ig_account["id"])


def _video_url(file_path: str) -> str:
    if not settings.public_base_url:
        raise InstagramNotConfigured(
            "PUBLIC_BASE_URL isn't set - Instagram fetches the video from a public URL rather than "
            "accepting a direct upload, so this backend needs a publicly reachable address before it "
            "can publish to Instagram."
        )
    return f"{settings.public_base_url.rstrip('/')}/media?path={quote(file_path)}"


def upload_video(
    file_path: str,
    title: str,
    tags: list[str] | None = None,
    poll_interval_seconds: float = 3.0,
    max_poll_attempts: int = 40,
) -> str:
    """Posts `file_path` as a Reel via the Content Publishing API's
    create -> poll -> publish flow and returns the resulting media id.
    Raises InstagramPublishFailed if Instagram reports the creation as
    ERROR/EXPIRED, or if it never leaves IN_PROGRESS.
    """
    import requests

    token = _load_token()
    if token is None:
        raise RuntimeError(
            f"No cached Instagram token at {settings.instagram_token_file} - connect an Instagram "
            "account from the dashboard's Settings page."
        )

    base = settings.instagram_api_base_url
    ig_user_id = token["ig_user_id"]
    access_token = token["page_access_token"]
    caption = title if not tags else f"{title} " + " ".join(f"#{t.lstrip('#')}" for t in tags)

    create_response = requests.post(
        f"{base}/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": _video_url(file_path),
            "caption": caption[:2200],
            "access_token": access_token,
        },
        timeout=30,
    )
    create_response.raise_for_status()
    create_data = create_response.json()
    if "error" in create_data:
        raise InstagramPublishFailed(f"Instagram media create failed: {create_data['error']}")
    creation_id = create_data["id"]

    for _ in range(max_poll_attempts):
        status_response = requests.get(
            f"{base}/{creation_id}", params={"fields": "status_code", "access_token": access_token}, timeout=30
        )
        status_response.raise_for_status()
        status_data = status_response.json()
        status = status_data.get("status_code")

        if status in ("ERROR", "EXPIRED"):
            raise InstagramPublishFailed(f"Instagram media {creation_id} failed: {status_data}")
        if status == "FINISHED":
            break

        time.sleep(poll_interval_seconds)
    else:
        raise InstagramPublishFailed(f"Instagram media {creation_id} never finished processing")

    publish_response = requests.post(
        f"{base}/{ig_user_id}/media_publish", data={"creation_id": creation_id, "access_token": access_token}, timeout=30
    )
    publish_response.raise_for_status()
    publish_data = publish_response.json()
    if "error" in publish_data:
        raise InstagramPublishFailed(f"Instagram publish failed: {publish_data['error']}")

    return publish_data["id"]
