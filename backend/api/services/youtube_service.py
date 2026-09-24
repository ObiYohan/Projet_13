import os
import re
import threading
import time
import unicodedata
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httplib2
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .language import detect_language, has_non_latin_letters, mentions_other_language

SEARCH_COST = 100
VIDEOS_LIST_COST = 1
QUOTA_TIMEZONE = ZoneInfo("America/Los_Angeles")  # YouTube quotas reset at midnight Pacific Time.

SEARCH_KEYWORDS = {
    "en": "chess opening tutorial|explanation|explained",
    "fr": "échecs ouverture|explication|tutoriel|cours",
}
MIN_DURATION_SECONDS = 3 * 60
MAX_DURATION_SECONDS = 2 * 60 * 60
MIN_VIEWS = 1000
SEARCH_RESULTS = 25

# Words too generic to tell openings apart ("defence"/"defense" also differ in spelling).
GENERIC_WORDS = {
    "defence", "defense", "opening", "game", "variation", "system", "the", "of",
    "partie", "ouverture", "debut", "variante", "variantes", "systeme", "de", "la", "le", "du", "des", "d",
}


class YouTubeServiceError(Exception):
    """Base error for failures while talking to the YouTube Data API."""


class YouTubeConfigError(YouTubeServiceError):
    """No API key is configured."""


class YouTubeTimeoutError(YouTubeServiceError):
    """The YouTube Data API did not respond in time."""


class YouTubeQuotaError(YouTubeServiceError):
    """The daily quota is (or would be) exhausted."""

    def __init__(self, message: str, retry_after: int) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class QuotaTracker:
    """Counts the units spent today so we stop before YouTube rejects us."""

    def __init__(self, daily_limit: int) -> None:
        self._daily_limit = daily_limit
        self._used = 0
        self._day = self._today()
        self._lock = threading.Lock()

    @staticmethod
    def _today():
        return datetime.now(QUOTA_TIMEZONE).date()

    @staticmethod
    def seconds_until_reset() -> int:
        now = datetime.now(QUOTA_TIMEZONE)
        tomorrow = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), QUOTA_TIMEZONE)
        return int((tomorrow - now).total_seconds()) + 1

    def reserve(self, units: int) -> None:
        with self._lock:
            if self._today() != self._day:
                self._day, self._used = self._today(), 0
            if self._used + units > self._daily_limit:
                raise YouTubeQuotaError(
                    "YouTube daily quota exhausted, try again after the reset (midnight Pacific Time).",
                    self.seconds_until_reset(),
                )
            self._used += units

    def exhaust(self) -> None:
        with self._lock:
            self._used = self._daily_limit


def no_videos_message(opening: str) -> str:
    return f"Aucune vidéo pertinente trouvée pour « {opening} »."


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", text.replace("'", "").replace("’", "")).strip()


def _required_words(opening: str) -> set[str]:
    """Distinctive words of the most specific part of the name
    ("Ruy Lopez, Berlin Defence" -> {"berlin"})."""
    words = set(_fold(opening.split(",")[-1]).split()) - GENERIC_WORDS
    return words or set(_fold(opening).split())


def _duration_seconds(iso_duration: str) -> int:
    match = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_duration or "")
    if not match:
        return 0
    days, hours, minutes, seconds = (int(g or 0) for g in match.groups())
    return ((days * 24 + hours) * 60 + minutes) * 60 + seconds


class YouTubeService:
    """Searches YouTube for explanatory videos about a chess opening."""

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 10.0,
        daily_quota: int | None = None,
        cache_ttl: float | None = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.environ.get("API_KEY_YOUTUBE")
        self._timeout = timeout
        self._quota = QuotaTracker(daily_quota or int(os.environ.get("YOUTUBE_DAILY_QUOTA", 10000)))
        self._cache_ttl = cache_ttl if cache_ttl is not None else float(
            os.environ.get("YOUTUBE_CACHE_TTL_SECONDS", 24 * 3600)
        )
        self._cache: dict[tuple, tuple[float, dict]] = {}
        self._cache_lock = threading.Lock()

    def search_videos(
        self,
        opening: str,
        max_results: int = 5,
        lang: str | None = None,
        aliases: tuple[str, ...] = (),
    ) -> dict:
        """Return {"query", "videos"} for `opening`, searched with `opening`'s name.

        `lang` ("fr" / "en") sets the search keywords and keeps only videos in
        that language; `aliases` (e.g. the name in the other language) are also
        accepted when checking that a video is about the opening. Results are
        cached, including empty ones."""
        if not self._api_key:
            raise YouTubeConfigError("API_KEY_YOUTUBE is not configured.")

        key = (_fold(opening), lang, tuple(sorted(_fold(a) for a in aliases)))
        with self._cache_lock:
            cached = self._cache.get(key)
        if cached and time.monotonic() - cached[0] < self._cache_ttl:
            result = cached[1]
        else:
            result = self._search(opening, lang, aliases)
            with self._cache_lock:
                self._cache[key] = (time.monotonic(), result)
        return {"query": result["query"], "videos": result["videos"][:max_results]}

    def _search(self, opening: str, lang: str | None, aliases: tuple[str, ...]) -> dict:
        name = " ".join(f'"{part.strip()}"' for part in opening.split(",") if part.strip())
        query = f"{name} {SEARCH_KEYWORDS.get(lang, SEARCH_KEYWORDS['en'])}"
        client = build("youtube", "v3", developerKey=self._api_key,
                       http=httplib2.Http(timeout=self._timeout), cache_discovery=False)

        search_params = {
            "part": "id", "q": query, "type": "video", "maxResults": SEARCH_RESULTS,
            "videoEmbeddable": "true", "videoSyndicated": "true", "safeSearch": "strict",
        }
        if lang:
            search_params["relevanceLanguage"] = lang
        found = self._execute(client.search().list(**search_params), SEARCH_COST)
        ids = [item["id"]["videoId"] for item in found.get("items", [])]

        videos = []
        if ids:
            details = self._execute(
                client.videos().list(part="snippet,contentDetails,statistics,status", id=",".join(ids)),
                VIDEOS_LIST_COST,
            )
            by_id = {item["id"]: item for item in details.get("items", [])}
            required = [_required_words(n) for n in (opening, *aliases) if n]
            for video_id in ids:  # keep YouTube's relevance order
                video = by_id.get(video_id)
                if video and self._is_relevant(video, required, lang):
                    videos.append(self._to_result(video))
        return {"query": query, "videos": videos}

    def _execute(self, request, cost: int) -> dict:
        self._quota.reserve(cost)
        try:
            return request.execute(num_retries=1)
        except HttpError as exc:
            if exc.resp.status == 403 and b"quotaExceeded" in (exc.content or b""):
                self._quota.exhaust()
                raise YouTubeQuotaError(
                    "YouTube daily quota exceeded.", QuotaTracker.seconds_until_reset()
                ) from exc
            raise YouTubeServiceError(f"YouTube API error {exc.resp.status}: {exc.reason}") from exc
        except TimeoutError as exc:
            raise YouTubeTimeoutError("Timed out while contacting the YouTube API.") from exc
        except OSError as exc:
            raise YouTubeServiceError(f"Failed to contact the YouTube API: {exc}") from exc

    @staticmethod
    def _is_relevant(video: dict, required: list[set[str]], lang: str | None) -> bool:
        snippet, status = video.get("snippet", {}), video.get("status", {})
        duration = _duration_seconds(video.get("contentDetails", {}).get("duration", ""))
        views = int(video.get("statistics", {}).get("viewCount", 0))
        title, description = snippet.get("title", ""), snippet.get("description", "")
        words = set(_fold(" ".join([title, description, " ".join(snippet.get("tags", []))])).split())
        return (
            status.get("embeddable", False)
            and status.get("privacyStatus") == "public"
            and snippet.get("liveBroadcastContent") == "none"
            and MIN_DURATION_SECONDS <= duration <= MAX_DURATION_SECONDS
            and views >= MIN_VIEWS
            and not has_non_latin_letters(title)
            and any(r <= words for r in required)
            and (lang is None or (
                YouTubeService._video_language(snippet) == lang and not mentions_other_language(title)
            ))
        )

    @staticmethod
    def _video_language(snippet: dict) -> str | None:
        """Language declared by the uploader, else guessed from the title and description."""
        declared = snippet.get("defaultAudioLanguage") or snippet.get("defaultLanguage")
        if declared:
            return declared.split("-")[0].lower()
        return detect_language(f"{snippet.get('title', '')} {snippet.get('description', '')}")

    @staticmethod
    def _to_result(video: dict) -> dict:
        snippet, stats = video["snippet"], video.get("statistics", {})
        thumbnails = snippet.get("thumbnails", {})
        thumbnail = (thumbnails.get("high") or thumbnails.get("medium") or thumbnails.get("default") or {})
        return {
            "video_id": video["id"],
            "title": snippet.get("title", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "published_at": snippet.get("publishedAt"),
            "duration_seconds": _duration_seconds(video["contentDetails"]["duration"]),
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats["likeCount"]) if "likeCount" in stats else None,
            "thumbnail_url": thumbnail.get("url"),
            "url": f"https://www.youtube.com/watch?v={video['id']}",
            "embed_url": f"https://www.youtube.com/embed/{video['id']}",
        }
