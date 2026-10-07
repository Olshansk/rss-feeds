"""Claude's resource migration and numbered JSON pagination regressions."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

import claude_blog as claude
from json_pages import fetch_numbered_items
from native_rss import generate_feed
from utils import save_rss_feed


class ClaudeTests(unittest.TestCase):
    def setUp(self):
        self.items = json.loads((Path(__file__).parent / "fixtures/claude_articles.json").read_text())

    def test_migration_retains_history_and_guids_and_rejects_bad_refresh(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("utils.get_feeds_dir", return_value=Path(tmp)),
            patch("feed_history.get_feeds_dir", return_value=Path(tmp)),
            patch.object(claude, "save_cache") as cache,
        ):
            old = claude.parse_posts(self.items)[0]
            old["link"] = old["guid"]
            old["title"] = "Previous title before correction"
            feed = generate_feed(
                [old], title="Claude", description="Archive", blog_url=claude.BLOG_URL, feed_name="claude"
            )
            save_rss_feed(feed, "claude")
            with patch.object(claude, "fetch_articles", return_value=self.items):
                self.assertTrue(claude.main())
            path = Path(tmp) / "feed_claude.xml"
            published = path.read_bytes()
            entries = ET.fromstring(published).findall("channel/item")
            self.assertEqual(len(entries), 2)
            self.assertEqual(entries[0].findtext("guid"), old["guid"])
            self.assertIn("/resources/articles/", entries[0].findtext("link"))
            self.assertEqual(entries[1].findtext("link"), self.items[1]["externalUrl"])
            self.assertEqual(cache.call_count, 1)
            for bad in ([], [{**self.items[0], "date": "invalid"}], [{**self.items[0], "slug": None}]):
                with patch.object(claude, "fetch_articles", return_value=bad), self.assertRaises(ValueError):
                    claude.main()
                self.assertEqual(path.read_bytes(), published)
                self.assertEqual(cache.call_count, 1)

    def test_full_archive_merges_categories_and_requires_complete_coverage(self):
        objects = [{"categoryOptions": [{"slug": "first"}, {"slug": "second"}]}, {"items": [], "total": 2}]
        with (
            patch.object(claude, "fetch_page", return_value="html"),
            patch.object(claude, "next_objects", return_value=objects),
        ):
            with patch.object(claude, "fetch_numbered_items", side_effect=[self.items[:1], self.items, self.items[:1]]):
                self.assertEqual(claude.fetch_articles(full=True), self.items)
            with (
                patch.object(claude, "fetch_numbered_items", return_value=self.items[:1]),
                self.assertRaisesRegex(ValueError, "Incomplete Claude archive"),
            ):
                claude.fetch_articles(full=True)

    def test_pagination_and_incremental_request_count(self):
        pages = [json.dumps({"items": [x], "total": 2}) for x in self.items]
        with patch("json_pages.fetch_page", side_effect=pages) as fetch:
            self.assertEqual(fetch_numbered_items("https://example.com", full=True), self.items)
            self.assertEqual(fetch.call_count, 2)
            self.assertTrue(fetch.call_args.args[0].endswith("page=2"))
        with patch("json_pages.fetch_page", side_effect=pages) as fetch:
            self.assertEqual(fetch_numbered_items("https://example.com"), self.items[:1])
            self.assertEqual(fetch.call_count, 1)

    def test_incomplete_or_repeated_pages_fail(self):
        first = json.dumps({"items": self.items[:1], "total": 2})
        for last in (first, json.dumps({"items": [], "total": 2}), "<html>challenge</html>"):
            with patch("json_pages.fetch_page", side_effect=[first, last]), self.assertRaises(ValueError):
                fetch_numbered_items("https://example.com", full=True)
        with patch("json_pages.fetch_page", return_value=first), self.assertRaisesRegex(ValueError, "exceeded"):
            fetch_numbered_items("https://example.com", full=True, max_pages=1)
        with patch("json_pages.fetch_page", return_value=first):
            self.assertEqual(
                fetch_numbered_items("https://example.com", full=True, max_pages=1, require_complete=False),
                self.items[:1],
            )
