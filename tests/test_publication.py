"""Offline checks for identity, failure reporting, dates, and safe publication."""

import subprocess
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch
from xml.etree import ElementTree as ET

from feedgen.feed import FeedGenerator

from dates import parse_date
from feed_history import merge_feed_history, require_posts
from models import FeedConfig
from run_all_feeds import run_feed
from utils import merge_entries, save_rss_feed, setup_feed_links, stable_fallback_date
from validate_feeds import validate_xml


class PublicationTests(unittest.TestCase):
    def test_dates_require_complete_date_and_preserve_timezone(self):
        self.assertEqual(parse_date("SEPT. 30, 2026"), datetime(2026, 9, 30, tzinfo=UTC))
        self.assertEqual(parse_date("2026-09-30T12:00:00-07:00").hour, 12)
        for value in ("2026", "Yesterday", "", "September 31, 2026"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_date(value)

    def test_cache_deduplicates_and_refreshes_without_changing_guid(self):
        old = {"link": "https://example.com/a", "title": "Old", "guid": "stable", "date": "2026-01-01T00:00:00+00:00"}
        new = {**old, "title": "Corrected", "guid": "different"}
        merged = merge_entries([new, new], [old, old])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["title"], "Corrected")
        self.assertEqual(merged[0]["guid"], "stable")
        with self.assertRaises(ValueError):
            require_posts([])

    def test_migration_matching_is_explicit_and_retains_archive(self):
        old = {"link": "https://old.com/a", "title": "Article", "guid": "stable", "date": parse_date("2026-01-01")}
        new = {**old, "link": "https://new.com/a", "guid": "new"}
        with patch("feed_history.load_feed_history", return_value=[old]):
            self.assertEqual(len(merge_feed_history([new], "example")), 2)
            merged = merge_feed_history([new], "example", match_titles=True)
            self.assertEqual(len(merged), 1)
            self.assertEqual(merged[0]["guid"], "stable")

    def test_atomic_publication_deduplicates_and_rejects_invalid_output(self):
        fg = FeedGenerator()
        fg.title("Example")
        fg.description("Example")
        setup_feed_links(fg, "https://example.com", "example")
        for day in (1, 2, 2):
            entry = fg.add_entry()
            entry.title(f"Post {day}")
            entry.link(href=f"https://example.com/{day}")
            entry.published(datetime(2026, 1, day, tzinfo=UTC))
        with tempfile.TemporaryDirectory() as tmp, patch("utils.get_feeds_dir", return_value=Path(tmp)):
            path = save_rss_feed(fg, "example")
            original = path.read_bytes()
            items = ET.fromstring(original).findall("channel/item")
            self.assertEqual([i.findtext("title") for i in items], ["Post 2", "Post 1"])
            self.assertTrue(all(i.findtext("guid") for i in items))
            entry = fg.add_entry()
            entry.title("Missing date")
            entry.link(href="https://example.com/bad")
            with self.assertRaises(ValueError):
                save_rss_feed(fg, "example")
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_undated_and_duplicate_xml_fails(self):
        item = "<item><title>A</title><link>https://example.com/a</link></item>"
        self.assertEqual(validate_xml(f"<rss><channel>{item}</channel></rss>".encode())["status"], "ERROR")
        dated = item.replace("</item>", "<pubDate>Thu, 01 Jan 2026 00:00:00 GMT</pubDate></item>")
        self.assertEqual(validate_xml(f"<rss><channel>{dated * 2}</channel></rss>".encode())["status"], "ERROR")

    def test_zero_exit_without_refresh_and_timeout_fail(self):
        config = FeedConfig(script="ollama_blog.py", type="requests", blog_url="https://ollama.com/blog")
        with tempfile.TemporaryDirectory() as tmp, patch("run_all_feeds.get_feeds_dir", return_value=Path(tmp)):
            with patch("run_all_feeds.subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="No posts")):
                self.assertFalse(run_feed("ollama", config))
            with patch("run_all_feeds.subprocess.run", side_effect=subprocess.TimeoutExpired("uv", 600)):
                self.assertFalse(run_feed("ollama", config))

    def test_fallback_date_is_stable_across_processes(self):
        value = subprocess.check_output(
            [
                sys.executable,
                "-c",
                "from utils import stable_fallback_date; print(stable_fallback_date('url').isoformat())",
            ],
            text=True,
        )
        self.assertEqual(value.strip(), stable_fallback_date("url").isoformat())


if __name__ == "__main__":
    unittest.main()
