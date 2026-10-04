"""Saved source fragments exercise the same parsers used by live generators."""

import importlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parent


class SourceTests(unittest.TestCase):
    def test_source_fragments(self):
        for case in json.loads((ROOT / "source_cases.json").read_text()):
            with self.subTest(source=case["module"]):
                parser = getattr(importlib.import_module(case["module"]), case["parser"])
                posts = parser((ROOT / "fixtures" / case["fixture"]).read_text())
                if isinstance(posts, tuple):
                    posts = posts[0]
                self.assertTrue(posts)
                self.assertEqual(len(posts), len({p["link"] for p in posts}))
                self.assertTrue(any(case["title"] in p["title"] for p in posts))
                self.assertTrue(any(p["date"].date().isoformat() == case["date"] for p in posts))
                for post in posts:
                    self.assertTrue(post["date"].tzinfo)
                    self.assertTrue(post["link"].startswith("https://"))


if __name__ == "__main__":
    unittest.main()
