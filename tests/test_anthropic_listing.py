"""Regression coverage for the October 2026 Anthropic team-page migration."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree

import anthropic_eng_blog as engineering
import anthropic_news_blog as news
import anthropic_red_blog as red
import anthropic_research_blog as research
from anthropic_listing import parse_team_listing


def article(team="engineering", slug="example"):
    return {
        "title": 'A "quoted" title λ',
        "slug": {"current": slug},
        "articleType": "research",
        "cardTeams": [{"slug": team}],
        "publishedOn": "2026-10-13",
        "summary": "Fresh summary\nSecond line.",
    }


def html(posts):
    data = (
        "a:"
        + json.dumps(
            {
                "initialGraphs": {"relatedArticles": [article(slug="unrelated")]},
                "initialPage": {"posts": posts, "hasNextPage": True},
            }
        )
        + "\n"
    )
    # Flight chunks can split an object, including inside a title or field name.
    return "".join(
        "<script>self.__next_f.push(" + json.dumps([1, part]) + ")</script>" for part in [data[:31], data[31:]]
    )


class TeamListingTests(unittest.TestCase):
    def test_listing_only_and_exact_text_across_chunks(self):
        post = article()
        result = engineering.parse_engineering_html(html([post]))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["link"], "https://www.anthropic.com/research/example")
        self.assertEqual(result[0]["title"], post["title"])
        self.assertEqual(result[0]["description"], post["summary"])
        self.assertEqual(result[0]["date"].isoformat(), "2026-10-13T00:00:00+00:00")

    def test_linked_url_is_preserved(self):
        post = {**article("frontier-red-team"), "linkedUrl": "/glasswing", "slug": None}
        self.assertEqual(red.parse_red_html(html([post]))[0]["link"], "https://www.anthropic.com/glasswing")

    def test_invalid_listing_fails_before_publishing_history(self):
        for module, team, fetch in [
            (engineering, "engineering", "fetch_engineering_content"),
            (red, "frontier-red-team", "fetch_red_content"),
        ]:
            for posts in [
                [],
                [article("wrong-team")],
                [{**article(team), "publishedOn": "invalid"}],
                [{**article(team), "title": ""}],
            ]:
                with (
                    self.subTest(module=module.__name__, posts=posts),
                    patch.object(module, fetch, return_value=html(posts)),
                    patch.object(module, "save_rss_feed") as save,
                ):
                    self.assertFalse(module.main())
                    save.assert_not_called()

    def test_moved_and_renamed_articles_keep_guids_and_archive(self):
        cases = [
            (
                engineering,
                "engineering",
                "fetch_engineering_content",
                "example",
                "https://www.anthropic.com/engineering/example",
            ),
            (
                red,
                "frontier-red-team",
                "fetch_red_content",
                "project-fetch-robot-dog",
                "https://red.anthropic.com/2025/project-fetch/",
            ),
        ]
        for module, team, fetch, slug, old_link in cases:
            with self.subTest(team=team), tempfile.TemporaryDirectory() as temp:
                directory = Path(temp)
                original = f"""<rss><channel><item><title>Old title</title><link>{old_link}</link><guid>stable-guid</guid><description>Old summary</description><pubDate>Tue, 13 Oct 2026 00:00:00 GMT</pubDate></item><item><title>Archive only</title><link>https://example.com/old</link><guid>archive-guid</guid><description>Archive body</description><pubDate>Mon, 12 Oct 2026 00:00:00 GMT</pubDate></item></channel></rss>"""
                path = directory / f"feed_{module.FEED_NAME}.xml"
                path.write_text(original)
                with (
                    patch("feed_history.get_feeds_dir", return_value=directory),
                    patch("utils.get_feeds_dir", return_value=directory),
                    patch.object(module, fetch, return_value=html([article(team, slug)])),
                ):
                    self.assertTrue(module.main())
                items = {i.findtext("guid"): i for i in ElementTree.parse(path).findall("./channel/item")}
                self.assertEqual(set(items), {"stable-guid", "archive-guid"})
                self.assertEqual(items["stable-guid"].findtext("title"), article()["title"])
                self.assertEqual(items["stable-guid"].findtext("description"), article()["summary"])
                self.assertEqual(items["archive-guid"].findtext("description"), "Archive body")

    def test_news_and_research_use_source_dates_and_summaries(self):
        for module, parser, kind in [
            (news, news.parse_news_html, "news"),
            (research, research.parse_research_html, "research"),
        ]:
            with self.subTest(module=module.__name__):
                post = {**article(), "articleType": kind, "cardTeams": None}
                parsed = parser(html([post]))
                self.assertEqual(len(parsed), 1)
                self.assertEqual(parsed[0]["date"].date().isoformat(), "2026-10-13")
                self.assertEqual(parsed[0]["description"], post["summary"])
                self.assertEqual(parsed[0]["category"], kind.title())

    def test_related_feeds_reject_empty_listing_before_xml_or_cache_writes(self):
        for module, fetch in [(news, "fetch_news_content"), (research, "fetch_research_content_selenium")]:
            with (
                self.subTest(module=module.__name__),
                patch.object(module, fetch, return_value=html([])),
                patch.object(module, "save_rss_feed") as save,
                patch.object(module, "save_cache") as cache,
            ):
                self.assertFalse(module.main())
                save.assert_not_called()
                cache.assert_not_called()

    def test_news_browser_returns_fresh_listing_without_legacy_expansion(self):
        source = html([{**article(), "articleType": "news", "cardTeams": None}])
        with patch.object(news, "setup_selenium_driver") as setup, patch.object(news, "WebDriverWait"):
            driver = setup.return_value
            driver.page_source = source
            self.assertEqual(news.fetch_news_content(), source)
            driver.find_element.assert_not_called()
            driver.quit.assert_called_once()

    def test_legacy_page_can_use_existing_parser(self):
        self.assertIsNone(parse_team_listing("<html>old page</html>", "engineering"))
