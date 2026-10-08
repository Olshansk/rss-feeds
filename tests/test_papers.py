"""Research metadata must be sourced, with coarse dates labeled explicitly."""

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch
from xml.etree import ElementTree as ET

import requests

from eleuther_papers_blog import generate_rss_feed, main, parse
from paper_dates import enrich_paper_dates
from utils import save_rss_feed


class PaperTests(unittest.TestCase):
    def test_library_and_arxiv_dates(self):
        posts = parse((Path(__file__).parent / "fixtures/eleuther.html").read_text())
        self.assertEqual(posts[0]["year"], 2026)
        response = Mock(
            content=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2609.01836v1</id><published>2026-09-02T12:00:00Z</published></entry></feed>'
        )
        with patch("paper_dates.requests.get", return_value=response):
            enriched = enrich_paper_dates(posts)
        self.assertEqual(enriched[0]["date"].date().isoformat(), "2026-09-02")

    def test_missing_api_record_fails(self):
        with patch("paper_dates.requests.get", return_value=Mock(content=b"<feed/>")), self.assertRaises(ValueError):
            enrich_paper_dates([{"link": "https://arxiv.org/abs/2609.01836", "year": 2026}])

    def test_year_precision_is_disclosed(self):
        posts = enrich_paper_dates([{"link": "https://example.org/paper", "year": 2025, "description": "Authors"}])
        self.assertEqual(posts[0]["date"].date().isoformat(), "2025-01-01")
        self.assertIn("publication year 2025 only", posts[0]["description"])

    def test_known_original_date_reused_across_arxiv_url_versions(self):
        date = datetime(2026, 9, 1, 20, 12, 8, tzinfo=UTC)
        history = [{"link": "https://arxiv.org/abs/2609.01836v1", "date": date}]
        live = [{"link": "https://arxiv.org/pdf/2609.01836v2", "title": "Updated title", "year": 2026}]
        with patch("paper_dates.requests.get") as get:
            enriched = enrich_paper_dates(live, known_posts=history)
        get.assert_not_called()
        self.assertEqual(enriched[0]["date"], date)
        self.assertEqual(enriched[0]["title"], "Updated title")
        self.assertNotIn("date", live[0])

    def test_only_unknown_dates_requested(self):
        known = {"link": "https://arxiv.org/abs/2609.01836", "date": datetime(2026, 9, 1, tzinfo=UTC)}
        live = [
            {"link": known["link"], "year": 2026},
            {"link": "https://arxiv.org/abs/2609.18605", "year": 2026},
        ]
        response = Mock(
            content=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/abs/2609.18605v1</id><published>2026-09-16T12:57:15Z</published></entry></feed>'
        )
        with patch("paper_dates.requests.get", return_value=response) as get:
            enriched = enrich_paper_dates(live, known_posts=[known])
        self.assertEqual(get.call_args.kwargs["params"], {"id_list": "2609.18605", "max_results": 1})
        self.assertEqual(enriched[0]["date"], known["date"])
        self.assertEqual(enriched[1]["date"].day, 16)

    def test_conflicting_known_dates_fail(self):
        link = "https://arxiv.org/abs/2609.01836"
        history = [{"link": link, "date": datetime(2026, 9, day, tzinfo=UTC)} for day in (1, 2)]
        with patch("paper_dates.requests.get") as get, self.assertRaisesRegex(ValueError, "Conflicting"):
            enrich_paper_dates([{"link": link}], known_posts=history)
        get.assert_not_called()

    def test_published_dates_and_ids_survive_fresh_listing_update(self):
        html = (Path(__file__).parent / "fixtures/eleuther.html").read_text()
        old = {
            **parse(html)[0],
            "title": "Old title",
            "date": datetime(2026, 9, 1, 20, 12, 8, tzinfo=UTC),
            "guid": "stable-subscriber-id",
        }
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("utils.get_feeds_dir", return_value=Path(tmp)),
            patch("feed_history.get_feeds_dir", return_value=Path(tmp)),
            patch("sys.argv", ["eleuther_papers_blog.py"]),
            patch("eleuther_papers_blog.fetch_page", return_value=html) as fetch,
            patch("paper_dates.requests.get", side_effect=AssertionError("Unnecessary metadata request")) as get,
        ):
            path = save_rss_feed(generate_rss_feed([old]), "eleuther_papers")
            original_date = ET.fromstring(path.read_bytes()).findtext("channel/item/pubDate")
            self.assertTrue(main())
            items = ET.fromstring(path.read_bytes()).findall("channel/item")
        fetch.assert_called_once()
        get.assert_not_called()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].findtext("guid"), old["guid"])
        self.assertEqual(items[0].findtext("pubDate"), original_date)
        self.assertEqual(items[0].findtext("title"), parse(html)[0]["title"])

    def test_live_date_takes_precedence_over_history(self):
        post = {"link": "https://arxiv.org/abs/2609.01836", "date": datetime(2026, 9, 2, tzinfo=UTC)}
        known = {**post, "date": datetime(2026, 9, 1, tzinfo=UTC)}
        with patch("paper_dates.requests.get") as get:
            self.assertEqual(enrich_paper_dates([post], known_posts=[known])[0]["date"], post["date"])
        get.assert_not_called()

    def test_missing_known_date_still_requires_api(self):
        for date in (None, "2026-09-01", datetime(2026, 9, 1)):
            with (
                self.subTest(date=date),
                patch("paper_dates.requests.get", return_value=Mock(content=b"<feed/>")) as get,
            ):
                post = {"link": "https://arxiv.org/abs/2609.01836", "year": 2026}
                with self.assertRaises(ValueError):
                    enrich_paper_dates([post], known_posts=[{**post, "date": date}])
                get.assert_called_once()

    def test_history_cannot_hide_live_listing_failure(self):
        with (
            patch("sys.argv", ["eleuther_papers_blog.py"]),
            patch("eleuther_papers_blog.fetch_page", return_value="<html/>") as fetch,
            patch("eleuther_papers_blog.save_rss_feed") as save,
            patch("paper_dates.requests.get") as get,
        ):
            self.assertFalse(main())
        fetch.assert_called_once()
        save.assert_not_called()
        get.assert_not_called()

    def test_new_paper_rate_limit_does_not_publish_history_only(self):
        html = (Path(__file__).parent / "fixtures/eleuther.html").read_text()
        known = {"link": "https://arxiv.org/abs/1906.06669", "date": datetime(2019, 6, 15, tzinfo=UTC)}
        response = requests.Response()
        response.status_code = 429
        with (
            patch("sys.argv", ["eleuther_papers_blog.py"]),
            patch("eleuther_papers_blog.fetch_page", return_value=html),
            patch("eleuther_papers_blog.load_feed_history", return_value=[known]),
            patch("paper_dates.requests.get", return_value=response),
            patch("eleuther_papers_blog.save_rss_feed") as save,
        ):
            self.assertFalse(main())
        save.assert_not_called()
