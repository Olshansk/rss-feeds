"""Regression checks for shared fetchers and source failure paths."""

import unittest
from unittest.mock import Mock, PropertyMock, patch

from selenium.common.exceptions import TimeoutException, WebDriverException

from dynamic_pages import fetch_rendered
from html_cards import parse_dated_cards
from native_rss import parse_rss


class SharedSourceTests(unittest.TestCase):
    def test_browser_closed_after_navigation_failure(self):
        driver = Mock()
        driver.get.side_effect = RuntimeError("Page unavailable")
        with patch("dynamic_pages.setup_selenium_driver", return_value=driver), self.assertRaises(RuntimeError):
            fetch_rendered("https://example.com", "article")
        driver.quit.assert_called_once()

    def test_article_timeout_reports_page_and_preserves_failure(self):
        driver = Mock(title="Just a moment...")
        with (
            patch("dynamic_pages.setup_selenium_driver", return_value=driver),
            patch("selenium.webdriver.support.ui.WebDriverWait") as wait,
        ):
            wait.return_value.until.side_effect = TimeoutException()
            with self.assertRaisesRegex(RuntimeError, "initial article listing.*Just a moment"):
                fetch_rendered("https://example.com", "article")
        driver.get.assert_called_once_with("https://example.com")
        driver.quit.assert_called_once()

    def test_navigation_timeout_survives_unavailable_browser_title(self):
        driver = Mock()
        driver.get.side_effect = TimeoutException()
        type(driver).title = PropertyMock(side_effect=WebDriverException())
        with (
            patch("dynamic_pages.setup_selenium_driver", return_value=driver),
            self.assertRaisesRegex(RuntimeError, "navigation.*page title='unavailable'"),
        ):
            fetch_rendered("https://example.com", "article")
        driver.quit.assert_called_once()

    def test_expansion_timeout_does_not_publish_partial_listing(self):
        driver = Mock(title="Example blog")
        driver.find_elements.return_value = [Mock()]
        with (
            patch("dynamic_pages.setup_selenium_driver", return_value=driver),
            patch("selenium.webdriver.support.ui.WebDriverWait") as wait,
        ):
            wait.return_value.until.side_effect = [True, TimeoutException()]
            with self.assertRaisesRegex(RuntimeError, "article expansion.*Example blog"):
                fetch_rendered("https://example.com", "article", button_xpath="//button", max_clicks=1)
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
