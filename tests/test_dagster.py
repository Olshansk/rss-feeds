"""Dagster's redesigned cards and publication failure boundaries."""

import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

import dagster_blog as dagster


class DagsterTests(unittest.TestCase):
    def setUp(self):
        self.html = (Path(__file__).parent / "fixtures/dagster_redesign.html").read_text()

    def test_redesigned_feature_and_cards_deduplicate(self):
        posts, next_page = dagster.parse_posts(self.html)
        self.assertIsNone(next_page)
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0]["title"], "The Data Plane Is Yours: Dagster Hybrid on Kubernetes and Azure")
        self.assertEqual(posts[0]["date"].date().isoformat(), "2026-09-08")
        self.assertIn("workload ownership", posts[0]["description"])
        self.assertEqual(
            posts[0]["link"], dagster.BLOG_URL + "/the-data-plane-is-yours-dagster-hybrid-on-kubernetes-and-azure"
        )

    def test_malformed_card_is_not_silently_skipped(self):
        for selector in ("h2", "a[href]", "time"):
            with self.subTest(missing=selector):
                soup = BeautifulSoup(self.html, "html.parser")
                soup.select_one("article").select_one(selector).decompose()
                with self.assertRaises(ValueError):
                    dagster.parse_posts(str(soup))

    def test_empty_live_listing_cannot_write_xml_or_cache(self):
        for entries in (
            [],
            [{"title": "Cached", "link": "https://dagster.io/blog/cached", "date": "2026-01-01T00:00:00+00:00"}],
        ):
            with (
                self.subTest(cached=bool(entries)),
                patch.object(dagster, "load_cache", return_value={"entries": entries}),
                patch("static_pages.fetch_page", return_value="<main>Empty</main>"),
                patch.object(dagster, "fetch_page", return_value="<main>Empty</main>"),
                patch.object(dagster, "save_rss_feed") as xml,
                patch.object(dagster, "save_cache") as cache,
            ):
                with self.assertRaises(ValueError):
                    dagster.main()
                xml.assert_not_called()
                cache.assert_not_called()
