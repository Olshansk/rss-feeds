"""Source summaries and duplicate cards in Timaeus's research listing."""

import unittest

from timaeus_blog import parse


class TimaeusTests(unittest.TestCase):
    def test_featured_summary_survives_duplicate_compact_card(self):
        articles = parse("""
            <a href="/research/2024-10-04-paper">
              <h3>Research paper</h3><p>Authors · Spotlight</p>
              <div class="mt-2 text-sm text-muted-foreground/80">
                <p>The source <em>summary</em>.</p>
              </div>
            </a>
            <a href="/research/2024-10-04-paper">
              <h3>Research paper</h3><p>Authors</p>
            </a>
        """)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["description"], "The source summary .")
        self.assertEqual(articles[0]["link"], "https://timaeus.co/research/2024-10-04-paper")
        self.assertEqual(articles[0]["date"].isoformat(), "2024-10-04T00:00:00+00:00")

    def test_compact_card_retains_author_fallback(self):
        articles = parse("""
            <a href="/research/2024-10-04-paper">
              <h3>Research paper</h3><p>Authors · ICLR</p>
            </a>
        """)
        self.assertEqual(articles[0]["description"], "Authors · ICLR")
