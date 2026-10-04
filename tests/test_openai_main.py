"""Coverage and failure isolation for the combined OpenAI subscription."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

import openai_main_blog

NEWS = """<rss><channel>
<item><title>Research and product</title><link>https://openai.com/index/example/</link>
<guid>original-news-id</guid><pubDate>Thu, 01 Jan 2026 00:00:00 GMT</pubDate>
<category>Research</category><category>Product</category><category>Future category</category></item>
<item><title>Uncategorized news</title><link>https://openai.com/index/other/</link>
<pubDate>Fri, 02 Jan 2026 00:00:00 GMT</pubDate></item>
</channel></rss>"""
DEVELOPER = """<a class="resource-item" href="/blog/developer-only">
<div class="line-clamp-2">Developer-only post</div>
<div class="text-secondary">Jan 3, 2026</div>
<p class="line-clamp-3">Developer summary</p>
<div class="pt-2 text-sm text-secondary">Guides</div></a>"""


class OpenAIMainTests(unittest.TestCase):
    def test_combined_publication_includes_all_categories_and_developer_posts(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("utils.get_feeds_dir", return_value=Path(tmp)),
            patch("feed_history.get_feeds_dir", return_value=Path(tmp)),
            patch.object(openai_main_blog, "fetch_page", side_effect=[NEWS, DEVELOPER + DEVELOPER]),
        ):
            openai_main_blog.main()
            channel = ET.parse(Path(tmp) / "feed_openai_main.xml").find("channel")
            items = channel.findall("item")
            self.assertEqual(
                [item.findtext("title") for item in items],
                ["Developer-only post", "Uncategorized news", "Research and product"],
            )
            self.assertEqual(items[-1].findtext("guid"), "original-news-id")
            self.assertEqual(
                [tag.text for tag in items[-1].findall("category")],
                ["Research", "Product", "Future category"],
            )
            self.assertEqual([tag.text for tag in items[0].findall("category")], ["Developer", "Guides"])
            self.assertEqual(channel.findtext("link"), openai_main_blog.BLOG_URL)

    def test_either_empty_source_preserves_previously_published_feed(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("utils.get_feeds_dir", return_value=Path(tmp)),
            patch("feed_history.get_feeds_dir", return_value=Path(tmp)),
        ):
            with patch.object(openai_main_blog, "fetch_page", side_effect=[NEWS, DEVELOPER]):
                openai_main_blog.main()
            path = Path(tmp) / "feed_openai_main.xml"
            original = path.read_bytes()
            for sources in [("<rss><channel/></rss>", DEVELOPER), (NEWS, "<html/>")]:
                with (
                    self.subTest(sources=sources),
                    patch.object(openai_main_blog, "fetch_page", side_effect=sources),
                    self.assertRaises(ValueError),
                ):
                    openai_main_blog.main()
                self.assertEqual(path.read_bytes(), original)
