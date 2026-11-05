"""Transluce listing migration and fail-before-write boundaries."""

import unittest
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

import transluce_blog as transluce


class TransluceTests(unittest.TestCase):
    def setUp(self):
        self.html = (Path(__file__).parent / "fixtures/transluce_redesign.html").read_text()

    def test_redesigned_research_docent_and_governance_cards(self):
        posts = transluce.parse(self.html)
        self.assertEqual(len(posts), 4)  # External evaluator-forum article remains excluded.
        self.assertEqual(posts[0]["title"], "Mass Producing Training Data with Surprising Side Effects")
        self.assertEqual(posts[0]["date"].date().isoformat(), "2026-11-04")
        self.assertIsNone(posts[0]["description"])
        self.assertIn("five archives", posts[1]["description"])
        self.assertEqual(posts[3]["date"].date().isoformat(), "2026-08-04")
        self.assertEqual(posts[3]["description"], "Surfacing misaligned behaviors in production coding agent traffic")
        self.assertEqual(posts[2]["date"].date().isoformat(), "2026-02-18")

    def test_malformed_card_fails_before_partial_publication(self):
        for selector in ("h3", "h3 a", ".whitespace-nowrap"):
            with self.subTest(missing=selector):
                soup = BeautifulSoup(self.html, "html.parser")
                soup.select_one("article").select_one(selector).decompose()
                with self.assertRaises(ValueError):
                    transluce.parse(str(soup))

    def test_each_required_listing_must_succeed_before_writing(self):
        for failed in range(3):
            pages = [self.html] * 3
            pages[failed] = "<main>Empty listing</main>"
            with (
                self.subTest(failed=failed),
                patch("sys.argv", ["transluce_blog.py"]),
                patch.object(transluce, "fetch_page", side_effect=pages),
                patch.object(transluce, "merge_feed_history") as history,
                patch.object(transluce, "save_rss_feed") as save,
            ):
                self.assertFalse(transluce.main())
                history.assert_not_called()
                save.assert_not_called()

    def test_all_listings_reach_history_and_publication(self):
        posts = transluce.parse(self.html)
        with (
            patch("sys.argv", ["transluce_blog.py"]),
            patch.object(transluce, "fetch_page", return_value=self.html) as fetch,
            patch.object(
                transluce, "load_feed_history", return_value=[{**posts[0], "description": "Published summary"}]
            ),
            patch.object(transluce, "merge_feed_history", return_value=posts) as history,
            patch.object(transluce, "save_rss_feed") as save,
        ):
            self.assertTrue(transluce.main())
            self.assertEqual([c.args[0] for c in fetch.call_args_list], list(transluce.LISTING_URLS))
            self.assertEqual(len(history.call_args.args[0]), 12)
            self.assertEqual(history.call_args.args[0][0]["description"], "Published summary")
            save.assert_called_once()
