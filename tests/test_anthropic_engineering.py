"""Keep the published text identical to nested Flight source strings."""

import json
import unittest

from anthropic_eng_blog import generate_rss_feed, parse_engineering_html


class EngineeringTextTests(unittest.TestCase):
    def test_quotes_unicode_newlines_and_literal_backslashes_survive_transport(self):
        title = 'The "think" tool: café and C:\\tools'
        summary = 'A "quoted" summary.\nUnicode: λ. Literal escape: \\n.'
        article = {
            "_type": "engineeringArticle",
            "publishedOn": "2026-05-25",
            "slug": {"current": "claude-think-tool"},
            "summary": summary,
            "title": title,
        }
        transport = json.dumps([1, "0:" + json.dumps(article, separators=(",", ":")) + "\n"])
        articles = parse_engineering_html(f"<script>self.__next_f.push({transport})</script>")
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["title"], title)
        self.assertEqual(articles[0]["description"], summary)
        from xml.etree import ElementTree

        item = ElementTree.fromstring(generate_rss_feed(articles).rss_str()).find("./channel/item")
        self.assertEqual(item.findtext("title"), title)
        self.assertEqual(item.findtext("description"), summary)
