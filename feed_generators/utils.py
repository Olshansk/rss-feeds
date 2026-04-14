"""Shared utilities for feed generators."""

import json
import logging
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytz
import requests
from feedgen.feed import FeedGenerator

from models import GlobalSettings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
)
DEFAULT_HEADERS = {"User-Agent": DEFAULT_USER_AGENT}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def setup_logging(name: str | None = None) -> logging.Logger:
    """Configure logging and return a logger for the calling module.

    Call once at module level: ``logger = setup_logging()``
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    if name is None:
        import inspect

        frame_info = inspect.stack()[1]
        frame = getattr(frame_info, "frame", frame_info[0])
        name = frame.f_globals.get("__name__", __name__)
    return logging.getLogger(name)


logger = setup_logging()

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def get_cache_dir() -> Path:
    """Get the cache directory path, creating it if needed."""
    cache_dir = get_project_root() / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def get_feeds_dir() -> Path:
    """Get the feeds directory path, creating it if needed."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def get_cache_file(feed_name: str) -> Path:
    """Get the cache file path for a feed.

    Args:
        feed_name: Feed identifier (e.g., "dagster", "cursor")

    Returns:
        Path to ``cache/<feed_name>_posts.json``
    """
    return get_cache_dir() / f"{feed_name}_posts.json"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def fetch_page(url: str, timeout: int = 30, headers: dict | None = None) -> str:
    """Fetch a page and return its HTML content.

    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        headers: Optional headers dict. Falls back to DEFAULT_HEADERS.

    Returns:
        Response text (HTML)
    """
    if headers is None:
        headers = DEFAULT_HEADERS
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------


def stable_fallback_date(identifier: str) -> datetime:
    """Generate a stable date from a URL or title hash.

    Used when a post has no parseable date. The hash ensures the same
    identifier always produces the same fallback date, preventing
    cache churn.
    """
    hash_val = abs(hash(identifier)) % 730
    epoch = datetime(2023, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)
    return epoch + timedelta(days=hash_val)


# ---------------------------------------------------------------------------
# Cache management
# ---------------------------------------------------------------------------


def load_cache(feed_name: str, entries_key: str = "entries") -> dict:
    """Load existing cache or return empty structure.

    Args:
        feed_name: Feed identifier used to locate the cache file.
        entries_key: Key under which entries are stored (default "entries").

    Returns:
        Dict with ``last_updated`` and the entries list.
    """
    cache_file = get_cache_file(feed_name)
    if cache_file.exists():
        try:
            with open(cache_file) as f:
                data = json.load(f)
                logger.info(f"Loaded cache with {len(data.get(entries_key, []))} entries")
                return data
        except json.JSONDecodeError:
            logger.warning(f"Corrupted cache file {cache_file}, starting fresh")
    logger.info("No cache file found, will do full fetch")
    return {"last_updated": None, entries_key: []}


def save_cache(feed_name: str, entries: list[dict], entries_key: str = "entries") -> None:
    """Save entries to cache file with automatic datetime serialization.

    Args:
        feed_name: Feed identifier used to locate the cache file.
        entries: List of entry dicts to cache.
        entries_key: Key under which entries are stored (default "entries").
    """
    cache_file = get_cache_file(feed_name)
    serializable = []
    for entry in entries:
        entry_copy = entry.copy()
        for key, value in entry_copy.items():
            if isinstance(value, datetime):
                entry_copy[key] = value.isoformat()
        serializable.append(entry_copy)

    data = {
        "last_updated": datetime.now(pytz.UTC).isoformat(),
        entries_key: serializable,
    }
    with open(cache_file, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved cache with {len(entries)} entries to {cache_file}")


def deserialize_entries(entries: list[dict], date_field: str = "date") -> list[dict]:
    """Convert cached entries back to proper format with datetime objects.

    Args:
        entries: List of entry dicts from cache.
        date_field: Key name for the date field to deserialize.

    Returns:
        Entries with ISO date strings converted back to datetime objects.
    """
    result = []
    for entry in entries:
        entry_copy = entry.copy()
        if isinstance(entry_copy.get(date_field), str):
            try:
                entry_copy[date_field] = datetime.fromisoformat(entry_copy[date_field])
            except ValueError:
                entry_copy[date_field] = stable_fallback_date(entry_copy.get("link", ""))
        result.append(entry_copy)
    return result


def merge_entries(
    new_entries: list[dict],
    cached_entries: list[dict],
    id_field: str = "link",
    date_field: str = "date",
) -> list[dict]:
    """Merge new entries into cache, deduplicate, and sort.

    Args:
        new_entries: Freshly fetched entries.
        cached_entries: Previously cached entries.
        id_field: Field used for deduplication (default "link").
        date_field: Field used for sorting (default "date").

    Returns:
        Merged and sorted list of entries.
    """
    existing_ids = {e[id_field] for e in cached_entries}
    merged = list(cached_entries)

    added_count = 0
    for entry in new_entries:
        if entry[id_field] not in existing_ids:
            merged.append(entry)
            existing_ids.add(entry[id_field])
            added_count += 1

    logger.info(f"Added {added_count} new entries to cache")
    return sort_posts_for_feed(merged, date_field=date_field)


# ---------------------------------------------------------------------------
# Feed generation
# ---------------------------------------------------------------------------


def setup_feed_links(fg: FeedGenerator, blog_url: str, feed_name: str) -> None:
    """Set up feed links correctly so <link> points to the blog, not the feed.

    In feedgen, link order matters:
    - rel="self" must be set FIRST (becomes <atom:link rel="self">)
    - rel="alternate" must be set LAST (becomes the main <link>)

    The repo slug is configurable via the RSS_REPO_SLUG environment variable,
    defaulting to "Olshansk/rss-feeds". Fork users can override it:
        RSS_REPO_SLUG=oborchers/rss-feeds uv run feed_generators/ollama_blog.py

    Args:
        fg: FeedGenerator instance
        blog_url: URL to the original blog (e.g., "https://dagster.io/blog")
        feed_name: Feed name for the self link (e.g., "dagster")
    """
    settings = GlobalSettings()
    fg.link(
        href=f"https://raw.githubusercontent.com/{settings.repo_slug}/main/feeds/feed_{feed_name}.xml",
        rel="self",
    )
    fg.link(href=blog_url, rel="alternate")


def sort_posts_for_feed(posts: list[dict[str, Any]], date_field: str = "date") -> list[dict[str, Any]]:
    """Sort posts so newest appears first in the final RSS feed.

    IMPORTANT: feedgen reverses the order when writing entries to XML.
    So we sort ASCENDING (oldest first) here, which becomes DESCENDING
    (newest first) in the final feed output.

    Args:
        posts: List of post dicts with date fields
        date_field: Key name for the date field (default: "date")

    Returns:
        Sorted list with posts ordered for correct feed output
    """
    posts_with_date = [p for p in posts if p.get(date_field) is not None]
    posts_without_date = [p for p in posts if p.get(date_field) is None]

    posts_with_date.sort(key=lambda x: x[date_field])

    return posts_with_date + posts_without_date


def save_rss_feed(fg: FeedGenerator, feed_name: str) -> Path:
    """Save an RSS feed to the feeds directory.

    Args:
        fg: Configured FeedGenerator instance.
        feed_name: Feed identifier (e.g., "dagster").

    Returns:
        Path to the written XML file.
    """
    feeds_dir = get_feeds_dir()
    output_file = feeds_dir / f"feed_{feed_name}.xml"
    fg.rss_file(str(output_file), pretty=True)
    logger.info(f"Saved RSS feed to {output_file}")
    return output_file


# ---------------------------------------------------------------------------
# Chrome / Selenium
# ---------------------------------------------------------------------------


def get_chrome_major_version() -> int | None:
    """Detect the installed Chrome major version.

    Returns the major version number (e.g., 146) or None if detection fails.
    This is needed because undetected_chromedriver auto-downloads the latest
    chromedriver, which may not match the installed Chrome version.
    """
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "google-chrome",
        "google-chrome-stable",
    ]
    for path in chrome_paths:
        try:
            result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5)
            match = re.search(r"(\d+)\.", result.stdout)
            if match:
                version = int(match.group(1))
                logger.info(f"Detected Chrome major version: {version}")
                return version
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    logger.warning("Could not detect Chrome version, using undetected_chromedriver default")
    return None


def setup_selenium_driver():
    """Set up a headless Selenium WebDriver with undetected-chromedriver.

    Automatically detects the installed Chrome version to avoid
    chromedriver version mismatches.
    """
    import undetected_chromedriver as uc

    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(f"--user-agent={DEFAULT_USER_AGENT}")
    version = get_chrome_major_version()
    return uc.Chrome(options=options, version_main=version)
