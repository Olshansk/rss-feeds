"""Goodfire layout migrations must preserve identities and fail before writing."""

import unittest
from unittest.mock import Mock, patch

from lxml import etree

import goodfire_blog as feed
from static_pages import fetch_page

CARD = """<a class="index-item is-featured" href="/research/already-clean">
<div class="tag-tiles"><span class="tag-tile">Fundamental Research</span>
<span class="tag-tile">Link post</span></div>
<h2>Neural Networks Are <em>Already</em> Clean</h2>
<div class="index-meta"><span>Nick Cammarata</span><span>October 15, 2026</span></div>
</a>"""


class GoodfireTests(unittest.TestCase):
    def test_current_cards_keep_source_metadata_and_url_identity(self):
        posts = feed.parse(CARD + CARD + '<a href="/research/other">Navigation</a>')
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["title"], "Neural Networks Are Already Clean")
        self.assertEqual(posts[0]["description"], "Fundamental Research, Link post")
        self.assertEqual(posts[0]["date"].isoformat(), "2026-10-15T00:00:00+00:00")
        item = etree.fromstring(feed.generate_rss_feed(posts).rss_str()).find("channel/item")
        self.assertEqual(item.findtext("guid"), "https://www.goodfire.ai/research/already-clean")
        self.assertEqual(item.findtext("link"), item.findtext("guid"))

    def test_empty_and_partial_malformed_pages_preserve_published_output(self):
        for html in [
            "",
            CARD + CARD.replace("already-clean", "undated").replace("October 15, 2026", "Undated"),
            CARD.replace("<h2>", "<p>").replace("</h2>", "</p>"),
        ]:
            with (
                self.subTest(html=html),
                patch("sys.argv", ["goodfire_blog.py"]),
                patch.object(feed, "fetch_page", return_value=html),
                patch.object(feed, "save_rss_feed") as save,
            ):
                self.assertFalse(feed.main())
                save.assert_not_called()

    def test_previous_webflow_layout_remains_supported(self):
        html = """<div class="blog-c-item"><a href="/research/old"><h3>Old article</h3></a>
        <div fs-list-field="category">Applied Research</div><div>July 7, 2026</div></div>"""
        post = feed.parse(html)[0]
        self.assertEqual(post["title"], "Old article")
        self.assertEqual(post["description"], "Applied Research")
        self.assertEqual(post["date"].date().isoformat(), "2026-07-07")


class SourceEncodingTests(unittest.TestCase):
    def test_explicit_utf8_preserves_titles_when_http_charset_is_missing(self):
        title = "They’re learning — with 30× fewer rollouts"  # noqa: RUF001 - exact source characters
        response = Mock(status_code=200, content=title.encode("utf-8"), text=title.encode("utf-8").decode("latin-1"))
        with patch("static_pages.requests.get", return_value=response):
            self.assertEqual(fetch_page("https://www.goodfire.ai/research", encoding="utf-8"), title)
            self.assertEqual(fetch_page("https://example.com"), response.text)
