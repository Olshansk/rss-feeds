"""Generate RSS feed for the AI FIRST Podcast (https://ai-first.ai/podcast).

Two-stage scraper: the listing page gives link + title, each episode page
then provides the date and description via a JSON-LD PodcastEpisode schema.
German-language podcast.
"""

import argparse
import json
import time
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
    DEFAULT_HEADERS,
    deserialize_entries,
    fetch_page,
    load_cache,
    save_cache,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "ai_first_podcast"
BLOG_URL = "https://ai-first.ai/podcast"
BASE_URL = "https://ai-first.ai"
DETAIL_FETCH_DELAY_SECONDS = 0.5


def parse_listing_page(html_content: str) -> list[dict]:
    """Extract (link, title) pairs from the podcast listing page."""
    soup = BeautifulSoup(html_content, "html.parser")
    episodes: list[dict] = []
    seen_hrefs: set[str] = set()

    for link in soup.select('a[href^="/podcast/"]'):
        href = link.get("href", "")
        if href.rstrip("/") == "/podcast" or href in seen_hrefs:
            continue
        seen_hrefs.add(href)

        # Prefer a heading inside the anchor (just the episode title). Fall back
        # to aria-label, then to separator-joined text -- the anchor contains
        # multiple sibling text nodes (episode number, guest, role) that must
        # not be concatenated without whitespace.
        title = None
        heading = link.select_one("h1, h2, h3, h4, h5, h6")
        if heading:
            title = heading.get_text(separator=" ", strip=True)
        if not title:
            aria = link.get("aria-label", "").strip()
            if aria:
                title = aria.removeprefix("Podcast: ").strip()
        if not title:
            text = link.get_text(separator=" ", strip=True)
            if text and len(text) > 5:
                title = text[:200]
                if len(text) > 200:
                    logger.debug(f"Fallback title for {href} truncated from {len(text)} chars")
        if not title:
            continue

        episodes.append({"link": f"{BASE_URL}{href}", "title": title})

    logger.info(f"Found {len(episodes)} episode links on listing page")
    return episodes


def fetch_episode_details(url: str) -> tuple[datetime | None, str]:
    """Return (date, description) for a single episode page."""
    try:
        html = fetch_page(url, timeout=15, headers=DEFAULT_HEADERS)
    except Exception as e:
        logger.warning(f"Failed to fetch episode page {url}: {e}")
        return None, ""

    soup = BeautifulSoup(html, "html.parser")

    # Primary: JSON-LD PodcastEpisode schema
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        if data.get("@type") != "PodcastEpisode":
            continue

        date = None
        date_str = data.get("datePublished")
        if date_str:
            try:
                date = datetime.fromisoformat(date_str)
                if date.tzinfo is None:
                    date = date.replace(tzinfo=pytz.UTC)
            except ValueError:
                pass

        return date, data.get("description", "")

    # Fallback: <time datetime="..."> element
    time_elem = soup.select_one("time[datetime]")
    if time_elem and time_elem.get("datetime"):
        try:
            date = datetime.fromisoformat(time_elem["datetime"].replace("Z", "+00:00"))
            if date.tzinfo is None:
                date = date.replace(tzinfo=pytz.UTC)
            return date, ""
        except ValueError:
            pass

    return None, ""


def enrich_episodes(stub_episodes: list[dict]) -> list[dict]:
    """Fetch detail page for each stub and return full episode dicts."""
    enriched = []
    for i, stub in enumerate(stub_episodes):
        date, description = fetch_episode_details(stub["link"])
        if not date:
            date = stable_fallback_date(stub["link"])
        enriched.append(
            {
                "title": stub["title"],
                "link": stub["link"],
                "date": date,
                "description": description or stub["title"],
            }
        )
        if i < len(stub_episodes) - 1:
            time.sleep(DETAIL_FETCH_DELAY_SECONDS)
        if (i + 1) % 10 == 0:
            logger.info(f"Fetched {i + 1}/{len(stub_episodes)} episode details")
    return enriched


def generate_rss_feed(episodes: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("AI FIRST Podcast")
    fg.description(
        "Der AI FIRST Podcast: Erfahre jeden Freitag aus erster Hand, wie Unternehmer und Führungskräfte AI einsetzen."
    )
    fg.language("de")
    fg.author({"name": "AI FIRST"})
    fg.logo("https://ai-first.ai/images/og/og-default.png")
    fg.subtitle("KI-Transformation, Produktivität und die Zukunft der Arbeit")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for ep in sort_posts_for_feed(episodes, date_field="date"):
        fe = fg.add_entry()
        fe.title(ep["title"])
        fe.description(ep["description"])
        fe.link(href=ep["link"])
        fe.id(ep["link"])
        if ep.get("date"):
            fe.published(ep["date"])

    logger.info(f"Generated RSS feed with {len(episodes)} entries")
    return fg


def main(full_reset: bool = False) -> bool:
    cache = load_cache(FEED_NAME)
    cached_entries = deserialize_entries(cache.get("entries", []))
    cached_links = {ep["link"] for ep in cached_entries}

    html = fetch_page(BLOG_URL, timeout=15, headers=DEFAULT_HEADERS)
    listing = parse_listing_page(html)
    if not listing:
        logger.warning("No episodes found on listing page.")
        return False

    if full_reset:
        stubs_to_fetch = listing
        logger.info(f"Full reset: fetching details for all {len(stubs_to_fetch)} episodes")
        all_episodes = enrich_episodes(stubs_to_fetch)
    else:
        stubs_to_fetch = [ep for ep in listing if ep["link"] not in cached_links]
        logger.info(f"Incremental: {len(stubs_to_fetch)} new episode(s) to fetch")
        new_episodes = enrich_episodes(stubs_to_fetch)
        all_episodes = list(cached_entries) + new_episodes

    all_episodes = sort_posts_for_feed(all_episodes, date_field="date")
    save_cache(FEED_NAME, all_episodes)

    feed = generate_rss_feed(all_episodes)
    save_rss_feed(feed, FEED_NAME)
    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate AI FIRST Podcast RSS feed")
    parser.add_argument("--full", action="store_true", help="Force full reset (re-fetch every episode)")
    args = parser.parse_args()
    main(full_reset=args.full)
