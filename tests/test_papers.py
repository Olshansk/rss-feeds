"""Research metadata must be sourced, with coarse dates labeled explicitly."""

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from eleuther_papers_blog import parse
from paper_dates import enrich_paper_dates


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
