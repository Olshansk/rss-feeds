"""Regression checks for shared fetchers and source failure paths."""

import unittest
from unittest.mock import Mock, patch

from requests import HTTPError, Response

from dynamic_pages import fetch_rendered, fetch_static_or_rendered
from html_cards import parse_dated_cards
from native_rss import parse_rss


class SharedSourceTests(unittest.TestCase):
    def test_browser_fallback_preserves_http_failure_semantics(self):
        for status in (403, 404, 500):
            response = Response()
            response.status_code = status
            with (
                self.subTest(status=status),
                patch("dynamic_pages.fetch_page", side_effect=HTTPError(response=response)),
                patch("dynamic_pages.fetch_rendered", return_value="article HTML") as browser,
            ):
                if status == 403:
                    self.assertEqual(fetch_static_or_rendered("https://example.com", "article"), "article HTML")
                    browser.assert_called_once()
                else:
                    with self.assertRaises(HTTPError):
                        fetch_static_or_rendered("https://example.com", "article")
                    browser.assert_not_called()

    def test_browser_closed_after_navigation_failure(self):
        driver = Mock()
        driver.get.side_effect = RuntimeError("Page unavailable")
        with patch("dynamic_pages.setup_selenium_driver", return_value=driver), self.assertRaises(RuntimeError):
            fetch_rendered("https://example.com", "article")
        driver.quit.assert_called_once()

    def test_empty_and_undated_native_feeds_fail(self):
        for xml in (
            "<html/>",
            "<rss><channel/></rss>",
            "<rss><channel><item><title>A</title><link>https://example.com</link></item></channel></rss>",
        ):
            with self.subTest(xml=xml), self.assertRaises(ValueError):
                parse_rss(xml)

    def test_broken_card_date_is_not_silently_skipped(self):
        html = '<a href="/post"><h2>Title</h2><time datetime="invalid">Today</time></a>'
        with self.assertRaises(ValueError):
            parse_dated_cards(html, "a", "https://example.com")
