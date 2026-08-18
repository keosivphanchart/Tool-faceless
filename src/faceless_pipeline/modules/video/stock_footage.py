"""Pull matching stock footage from Pexels/Pixabay based on script keywords."""
import logging
from pathlib import Path

import requests

from faceless_pipeline.config import settings

logger = logging.getLogger(__name__)

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
PIXABAY_SEARCH_URL = "https://pixabay.com/api/videos/"


def search_pexels(query: str, per_page: int = 5, orientation: str = "portrait") -> list[dict]:
    if not settings.pexels_api_key:
        return []
    response = requests.get(
        PEXELS_SEARCH_URL,
        headers={"Authorization": settings.pexels_api_key},
        params={"query": query, "per_page": per_page, "orientation": orientation},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return [
        {
            "id": v["id"],
            "url": max(v["video_files"], key=lambda f: f.get("width", 0))["link"],
            "source": "pexels",
        }
        for v in data.get("videos", [])
    ]


def search_pixabay(query: str, per_page: int = 5) -> list[dict]:
    if not settings.pixabay_api_key:
        return []
    response = requests.get(
        PIXABAY_SEARCH_URL,
        params={"key": settings.pixabay_api_key, "q": query, "per_page": per_page, "video_type": "film"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return [
        {"id": v["id"], "url": v["videos"]["medium"]["url"], "source": "pixabay"}
        for v in data.get("hits", [])
    ]


def download_clip(url: str, out_path: str) -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return out_path


def fetch_background_clips(keywords: list[str], out_dir: str, clips_needed: int = 1) -> list[str]:
    """Searches Pexels first, then Pixabay, for each keyword until enough
    clips are found; downloads them to out_dir and returns local paths."""
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    paths: list[str] = []

    for keyword in keywords:
        if len(paths) >= clips_needed:
            break
        results = search_pexels(keyword) or search_pixabay(keyword)
        for clip in results:
            if len(paths) >= clips_needed:
                break
            local_path = str(Path(out_dir) / f"{clip['source']}_{clip['id']}.mp4")
            try:
                download_clip(clip["url"], local_path)
                paths.append(local_path)
            except Exception:
                logger.exception("Failed to download clip %s", clip["url"])

    if not paths:
        logger.warning(
            "No stock footage found/downloaded for keywords=%s "
            "(check PEXELS_API_KEY/PIXABAY_API_KEY). Caller should supply a fallback background.",
            keywords,
        )

    return paths
