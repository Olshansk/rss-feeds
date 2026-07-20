"""Shared logic for Apollo Research section feeds (Science, Governance, Monitoring).

All three sections live on https://www.apolloresearch.ai/ and are served as
static, server-rendered HTML (WordPress + Alpine.js filters), so plain
``requests`` + BeautifulSoup is sufficient.

The three sections use slightly different card markup:
  - Science / Governance: ``div.block`` cards with an ``h4`` title and a
    ``div.date`` (e.g. "September 17, 2025").
  - Monitoring: ``div.product-single`` cards with an ``h3`` title, a
    ``div.product-single__entry`` description, and a
    ``div.product-single__date`` (e.g. "17/02/2026", DD/MM/YYYY).

Date extraction is deliberately not tied to a single class name: card markup
differs per section and can change, so ``_find_card_date`` searches any
date-ish element and falls back to a regex scan of the card text. A card that
still yields no date logs a warning before using a hash-derived fallback, so a
missed selector surfaces during validation instead of silently producing
"STALE" items.

The parser below is deliberately layout-agnostic: it finds every anchor that
points to an article under ``/<section>/<slug>/`` and walks up to the nearest
enclosing element that contains a heading, then pulls the title, date, and
description from within that card.
"""

import argparse
import re
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
    fetch_page,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

BASE_URL = "https://www.apolloresearch.ai"

# Date formats seen on Apollo cards, plus reasonable fallbacks.
DATE_FORMATS = [
    "%B %d, %Y",  # September 17, 2025
    "%b %d, %Y",  # Sep 17, 2025
    "%B %Y",  # September 2025
    "%Y-%m-%d",  # 2025-09-17
    "%d/%m/%Y",  # 17/02/2026 (Monitoring, DD/MM/YYYY)
]

# Loose patterns for spotting a date substring anywhere in a card's text.
_DATE_PATTERNS = [
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{4}\b"),  # 17/02/2026
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),  # 2026-02-17
    re.compile(
        r"\b(?:January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+\d{1,2},\s+\d{4}\b"
    ),  # September 17, 2025
]


def parse_date(date_text):
    """Parse a card date string into a UTC datetime, or None if unparseable."""
    if not date_text:
        return None
    text = date_text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=pytz.UTC)
        except ValueError:
            continue
    logger.warning(f"Could not parse date: {date_text!r}")
    return None


def _find_card_date(card):
    """Return a parsed date for a card, or None if none can be found.

    Tries, in order: any element whose class contains "date", a ``<time>``
    element, then a regex scan over the card's full text. This keeps date
    extraction working across the sections' differing markup instead of
    depending on one hard-coded class name.
    """

    # Elements whose class mentions "date" (div.date, div.product-single__date, ...).
    def _class_has_date(classes):
        return classes and any("date" in c for c in classes)

    for el in card.find_all(class_=_class_has_date):
        parsed = parse_date(el.get_text(strip=True))
        if parsed:
            return parsed

    time_el = card.find("time")
    if time_el:
        parsed = parse_date(time_el.get_text(strip=True))
        if parsed:
            return parsed

    # Last resort: scan the whole card's text for a date-shaped substring.
    text = card.get_text(" ", strip=True)
    for pattern in _DATE_PATTERNS:
        match = pattern.search(text)
        if match:
            parsed = parse_date(match.group(0))
            if parsed:
                return parsed

    return None


def _find_card(anchor):
    """Walk up from an anchor to the nearest ancestor containing a heading."""
    node = anchor
    for _ in range(6):
        node = node.parent
        if node is None:
            return None
        if node.find(["h3", "h4"]):
            return node
    return None


def parse_section_html(html_content, section):
    """Extract article dicts for a given Apollo section from page HTML.

    Args:
        html_content: Raw HTML of the section landing page.
        section: URL segment, e.g. "science", "governance", "monitoring".

    Returns:
        List of dicts with title / link / description / date keys.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []
    seen_links = set()

    # Article URLs look like /<section>/<slug>/ ; exclude the section index page.
    slug_re = re.compile(rf"/{re.escape(section)}/[^/]+/?$")

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if not slug_re.search(href):
            continue
        # Normalize away query/fragment and skip the index page itself.
        link = href.split("?")[0].split("#")[0]
        if link.rstrip("/").endswith(f"/{section}"):
            continue
        if link in seen_links:
            continue

        card = _find_card(anchor)
        if card is None:
            continue

        heading = card.find(["h3", "h4"])
        title = heading.get_text(strip=True) if heading else ""
        if not title:
            continue

        seen_links.add(link)

        pub_date = _find_card_date(card)
        if pub_date is None:
            # No parseable date on the card. Warn loudly (a changed/missed
            # selector should surface here rather than silently produce a
            # "STALE" item) and fall back to a stable hash-derived date so
            # ordering stays deterministic and the cache doesn't churn.
            logger.warning(f"No parseable date for {link} - using stable fallback date")
            pub_date = stable_fallback_date(link)

        # Description: Monitoring cards have a summary; Science/Governance don't,
        # so fall back to the category tag, then the title.
        entry = card.find("div", class_="product-single__entry")
        if entry:
            description = entry.get_text(" ", strip=True)
        else:
            cat = card.find("div", class_="cat") or card.find("li")
            description = cat.get_text(strip=True) if cat else title

        articles.append(
            {
                "title": title,
                "link": link,
                "description": description,
                "date": pub_date,
            }
        )

    logger.info(f"Parsed {len(articles)} articles from Apollo {section} page")
    return articles


def generate_rss_feed(articles, feed_name, feed_title, feed_description, blog_url):
    """Build a FeedGenerator from parsed Apollo articles."""
    fg = FeedGenerator()
    fg.title(feed_title)
    fg.description(feed_description)
    fg.language("en")
    fg.author({"name": "Apollo Research"})
    setup_feed_links(fg, blog_url=blog_url, feed_name=feed_name)

    for post in sort_posts_for_feed(articles):
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["link"])
        fe.published(post["date"])
        fe.id(post["link"])

    return fg


def run_section(section, feed_name, feed_title, feed_description, blog_url):
    """End-to-end feed generation for one Apollo section.

    Supports an optional positional ``html_file`` argument for running against a
    locally saved copy of the page instead of fetching it live.

    Returns True on success, False if no articles were found (so the existing
    feed is left untouched rather than overwritten with an empty one).
    """
    parser = argparse.ArgumentParser(description=f"Generate the Apollo {section} RSS feed")
    parser.add_argument("html_file", nargs="?", help="Optional local HTML file to parse instead of fetching")
    args = parser.parse_args()

    try:
        if args.html_file:
            logger.info(f"Reading local HTML file: {args.html_file}")
            with open(args.html_file, encoding="utf-8") as f:
                html_content = f.read()
        else:
            html_content = fetch_page(blog_url)

        articles = parse_section_html(html_content, section)

        if not articles:
            logger.warning("No articles found - skipping feed update to avoid overwriting with empty feed")
            return False

        fg = generate_rss_feed(articles, feed_name, feed_title, feed_description, blog_url)
        save_rss_feed(fg, feed_name)
        return True

    except Exception as e:
        logger.error(f"Failed to generate Apollo {section} feed: {e!s}")
        return False
