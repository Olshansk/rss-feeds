"""Specific regressions behind silent feed freezes and repeated articles."""

import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import deeplearningai_the_batch as batch
import paulgraham_blog as pg
from feed_history import merge_feed_history


class RegressionTests(unittest.TestCase):
    def test_batch_publisher_migration_preserves_public_url_identity(self):
        content = (Path(__file__).parent / "fixtures/the_batch.xml").read_text()
        posts = batch.parse_batch_feed(content)
        self.assertEqual(posts[0]["link"], "https://www.deeplearning.ai/the-batch/issue-373")
        self.assertEqual(posts[0]["guid"], posts[0]["link"])
        previous = {**posts[0], "guid": "already-published-id"}
        with patch("feed_history.load_feed_history", return_value=[previous]):
            merged = merge_feed_history(posts, "the_batch")
        self.assertEqual(merged[0]["guid"], "already-published-id")

    def test_batch_rejects_unexpected_publisher_links(self):
        content = (Path(__file__).parent / "fixtures/the_batch.xml").read_text()
        with self.assertRaisesRegex(ValueError, "Unexpected Batch publisher"):
            batch.parse_batch_feed(content.replace("charonhub.deeplearning.ai", "unrelated.example"))

    def test_repeated_essays_fetched_once(self):
        html = '<font size="2"><a href="same.html">Title</a><a href="same.html">Title</a></font>'
        with (
            patch.object(pg, "fetch_page", return_value="article") as fetch,
            patch.object(pg, "get_article_content", return_value=("Body", datetime(2026, 8, 1, tzinfo=UTC))),
        ):
            posts = pg.parse_essays_page(html)
        self.assertEqual(len(posts), 1)
        fetch.assert_called_once()
