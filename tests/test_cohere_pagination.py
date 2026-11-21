"""Cohere archive growth and fail-before-write pagination limits."""

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

import cohere_blog as feed


class CoherePaginationTests(unittest.TestCase):
    @staticmethod
    def page(url):
        number = int(parse_qs(urlparse(url).query).get("page", [1])[0])
        more = f'<a href="/blog?page={number + 1}">Next</a>' if number < 31 else ""
        return f'<main><a href="/blog/article-{number}"><p>Article {number}</p><p>Nov 1, 2026</p></a>{more}</main>'

    def test_full_archive_includes_page_31(self):
        with patch("static_pages.fetch_page", side_effect=self.page) as fetch:
            posts = feed.fetch_all_posts()
        self.assertEqual(len(posts), 31)
        self.assertEqual(posts[-1]["link"], "https://cohere.com/blog/article-31")
        self.assertEqual(fetch.call_count, 31)

    def test_limit_exceeded_does_not_write_feed_or_cache(self):
        original_fetch = feed.fetch_all_posts
        with (
            patch("static_pages.fetch_page", side_effect=self.page),
            patch.object(feed, "load_cache", return_value={}),
            patch.object(feed, "fetch_all_posts", wraps=lambda: original_fetch(30)),
            patch.object(feed, "save_rss_feed") as save_feed,
            patch.object(feed, "save_cache") as save_cache,
            self.assertRaisesRegex(ValueError, "Pagination exceeded 30"),
        ):
            feed.main()
        save_feed.assert_not_called()
        save_cache.assert_not_called()
