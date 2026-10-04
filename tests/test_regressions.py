"""Specific regressions behind silent feed freezes and repeated articles."""

import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import deeplearningai_the_batch as batch
import paulgraham_blog as pg


class RegressionTests(unittest.TestCase):
    def test_repeated_essays_fetched_once(self):
        html = '<font size="2"><a href="same.html">Title</a><a href="same.html">Title</a></font>'
        with (
            patch.object(pg, "fetch_page", return_value="article") as fetch,
            patch.object(pg, "get_article_content", return_value=("Body", datetime(2026, 8, 1, tzinfo=UTC))),
        ):
            posts = pg.parse_essays_page(html)
        self.assertEqual(len(posts), 1)
        fetch.assert_called_once()

    def test_batch_ignores_bundled_error_markup(self):
        html = (Path(__file__).parent / "fixtures/the_batch.html").read_text() + '<script>"Page not found"</script>'
        with patch.object(batch, "fetch_page", return_value=html):
            self.assertTrue(batch.fetch_all_articles(max_pages=1))

    def test_batch_empty_page_fails(self):
        with patch.object(batch, "fetch_page", return_value="<html/>"), self.assertRaises(ValueError):
            batch.fetch_all_articles(max_pages=1)
