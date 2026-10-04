"""Exercise the production writer and subprocess runner without a live website."""

import os
from datetime import UTC, datetime
from pathlib import Path

from feedgen.feed import FeedGenerator

import utils

output = Path(os.environ["RSS_TEST_OUTPUT"])
utils.get_feeds_dir = lambda: output

if os.environ.get("RSS_TEST_SKIP_WRITE") != "1":
    feed = FeedGenerator()
    feed.title("Offline fixture")
    feed.description("Synthetic articles for CI")
    utils.setup_feed_links(feed, "https://example.invalid/blog", "fixture")
    feed.lastBuildDate(datetime(2026, 1, int(os.environ["RSS_TEST_BUILD_DAY"]), tzinfo=UTC))
    entry = feed.add_entry()
    entry.title(os.environ.get("RSS_TEST_TITLE", "Fixture article"))
    entry.link(href="https://example.invalid/article")
    entry.id("stable-fixture-guid")
    entry.published(datetime(2026, 1, 1, tzinfo=UTC))
    entry.description("Fixture summary")
    utils.save_rss_feed(feed, "fixture")
