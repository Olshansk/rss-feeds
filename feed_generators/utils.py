"""Shared utilities for feed generators."""

import hashlib
import json
import logging
import os
import re
import tempfile
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import pytz
from feedgen.feed import FeedGenerator
from lxml import etree

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
from dynamic_pages import get_chrome_major_version, setup_selenium_driver  # noqa: F401
from models import GlobalSettings
from static_pages import DEFAULT_HEADERS, DEFAULT_USER_AGENT, fetch_page  # noqa: F401

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
# Text sanitization
# ---------------------------------------------------------------------------

# XML 1.0 forbids NULL bytes and most C0/C1 control characters.
_INVALID_XML_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_RSS_ITEM_RE = re.compile(rb"(?m)^[ \t]*<item(?:\s[^>]*)?>.*?</item>[ \t]*(?:\r?\n|$)", re.DOTALL)


def sanitize_xml(text: str) -> str:
    """Strip characters that are invalid in XML 1.0 from *text*."""
    return _INVALID_XML_RE.sub("", text)


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
# Date helpers
# ---------------------------------------------------------------------------


def stable_fallback_date(identifier: str) -> datetime:
    """Generate a stable date from a URL or title hash.

    Used when a post has no parseable date. The hash ensures the same
    identifier always produces the same fallback date, preventing
    cache churn.
    """
    hash_val = int.from_bytes(hashlib.sha256(identifier.encode()).digest()[:4], "big") % 730
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
    merged = {entry[id_field]: entry for entry in deserialize_entries(cached_entries, date_field)}
    for entry in deserialize_entries(new_entries, date_field):
        previous = merged.get(entry[id_field], {})
        merged[entry[id_field]] = {**previous, **entry}
        if previous.get("guid"):
            merged[entry[id_field]]["guid"] = previous["guid"]
    return sort_posts_for_feed(list(merged.values()), date_field=date_field)


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


def _sort_rss_items(xml_bytes: bytes) -> bytes:
    """Sort dated RSS items newest-first while preserving undated items.

    How:
    1. Parse the serialized RSS document.
    2. Separate channel items with valid, missing, and invalid publication dates.
    3. Sort dated items descending by their parsed RFC 2822 dates.
    4. Append undated items after dated items in their original relative order.
    5. Reorder the original item byte blocks so content and formatting remain unchanged.

    Args:
        xml_bytes: Serialized RSS XML produced by ``FeedGenerator``.

    Returns:
        Serialized RSS XML with dated items ordered newest-first.
    """
    root = etree.fromstring(xml_bytes)
    channel = root.find("channel")
    if channel is None:
        return xml_bytes

    items = channel.findall("item")
    if len(items) < 2:
        return xml_bytes

    dated_items: list[tuple[datetime, int, etree._Element]] = []
    undated_items: list[tuple[int, etree._Element]] = []
    for index, item in enumerate(items):
        date_element = item.find("pubDate")
        date_text = date_element.text.strip() if date_element is not None and date_element.text else ""
        if not date_text:
            undated_items.append((index, item))
            continue

        try:
            parsed_date = parsedate_to_datetime(date_text)
            if parsed_date.tzinfo is None:
                parsed_date = parsed_date.replace(tzinfo=UTC)
            dated_items.append((parsed_date, index, item))
        except (TypeError, ValueError):
            logger.warning("Could not parse RSS item date %r; preserving its relative position", date_text)
            undated_items.append((index, item))

    ordered_indexes = [index for _, index, _ in sorted(dated_items, key=lambda value: value[0], reverse=True)]
    ordered_indexes.extend(index for index, _ in undated_items)
    if ordered_indexes == list(range(len(items))):
        return xml_bytes

    item_matches = list(_RSS_ITEM_RE.finditer(xml_bytes))
    if len(item_matches) != len(items):
        raise ValueError("Could not safely locate all RSS item blocks for reordering")

    first_match = item_matches[0]
    last_match = item_matches[-1]
    reordered_items = b"".join(item_matches[index].group(0) for index in ordered_indexes)
    return xml_bytes[: first_match.start()] + reordered_items + xml_bytes[last_match.end() :]


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
    from validate_feeds import validate_xml

    xml = _sort_rss_items(fg.rss_str(pretty=True))
    tree = etree.fromstring(xml)
    channel = tree.find("channel")
    links, guids = set(), set()
    changed = False
    for item in list(channel.findall("item")):
        link, guid = item.findtext("link"), item.findtext("guid")
        if link in links or (guid and guid in guids):
            channel.remove(item)
            changed = True
            continue
        links.add(link)
        guids.add(guid)
        if not guid and link:
            etree.SubElement(item, "guid", isPermaLink="false").text = link
            changed = True
    if changed:
        xml = etree.tostring(tree, xml_declaration=True, encoding="utf-8", pretty_print=True)
    result = validate_xml(xml, output_file.name)
    if result["status"] in {"ERROR", "EMPTY"}:
        raise ValueError(result["message"])
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=feeds_dir, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(xml)
        os.replace(temporary, output_file)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
    logger.info(f"Saved RSS feed to {output_file}")
    return output_file
