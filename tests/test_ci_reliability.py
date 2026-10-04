"""Offline regression checks for real generation, source failures, and CI churn."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.etree import ElementTree as ET

import requests

import deeplearningai_the_batch as batch
from models import FeedConfig, load_feed_registry
from run_all_feeds import run_feed
from utils import _preserve_unchanged_feed

FIXTURES = Path(__file__).parent / "fixtures"


class CIReliabilityTests(unittest.TestCase):
    def test_real_offline_generator_is_stable_but_must_write_each_run(self):
        config = FeedConfig(
            script=str((FIXTURES / "offline_generator.py").resolve()),
            type="requests",
            blog_url="https://example.invalid/blog",
        )
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            summary = folder / "summary.md"
            with (
                patch("run_all_feeds.get_feeds_dir", return_value=folder),
                patch.dict(
                    os.environ,
                    {
                        "RSS_TEST_OUTPUT": tmp,
                        "RSS_TEST_BUILD_DAY": "1",
                        "GITHUB_STEP_SUMMARY": str(summary),
                        "UV_OFFLINE": "true",
                        "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "feed_generators"),
                    },
                ),
            ):
                self.assertTrue(run_feed("fixture", config))
                path = folder / "feed_fixture.xml"
                original = path.read_bytes()
                os.utime(path, ns=(1, 1))
                os.environ["RSS_TEST_BUILD_DAY"] = "2"
                self.assertTrue(run_feed("fixture", config))
                self.assertEqual(path.read_bytes(), original)
                self.assertNotEqual(path.stat().st_mtime_ns, 1)

                os.environ["RSS_TEST_TITLE"] = "Corrected article"
                self.assertTrue(run_feed("fixture", config))
                updated = path.read_bytes()
                self.assertNotEqual(updated, original)
                self.assertEqual(ET.fromstring(updated).findtext("channel/item/guid"), "stable-fixture-guid")

                os.environ["RSS_TEST_SKIP_WRITE"] = "1"
                self.assertFalse(run_feed("fixture", config))
                self.assertEqual(path.read_bytes(), updated)
                self.assertIn("exited without writing fresh output", summary.read_text())
                self.assertIn("| 4 | ❌ | fixture |", summary.read_text())

    def test_batch_fixture_publishes_but_http_failure_preserves_it(self):
        good = requests.Response()
        good.status_code = 200
        good._content = (FIXTURES / "the_batch.xml").read_bytes()
        good.encoding = "utf-8"
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("utils.get_feeds_dir", return_value=Path(tmp)),
            patch("feed_history.get_feeds_dir", return_value=Path(tmp)),
            patch("static_pages.requests.get", return_value=good) as fetch,
        ):
            self.assertTrue(batch.main())
            self.assertEqual(fetch.call_count, 1)
            path = Path(tmp) / "feed_the_batch.xml"
            published = path.read_bytes()
            self.assertEqual(len(ET.fromstring(published).findall("channel/item")), 1)
            for status in (403, 429, 503):
                response = requests.Response()
                response.status_code = status
                response.url = batch.SOURCE_URL
                response._content = b"<html><title>Just a moment...</title></html>"
                response.headers.update({"Retry-After": "3600", "cf-mitigated": "challenge"})
                fetch.return_value = response
                fetch.reset_mock()
                with (
                    self.subTest(status=status),
                    self.assertLogs("static_pages", level="ERROR") as logs,
                    self.assertRaises(requests.HTTPError),
                ):
                    batch.main()
                self.assertEqual(fetch.call_count, 1)
                self.assertEqual(path.read_bytes(), published)
                self.assertIn("Retry-After", "\n".join(logs.output))
                self.assertIn("cf-mitigated", "\n".join(logs.output))

    def test_comparison_retains_real_metadata_changes_and_repairs_bad_history(self):
        original = b"<rss><channel><title>Old</title><lastBuildDate>A</lastBuildDate></channel></rss>"
        changed = original.replace(b"Old", b"New").replace(b">A<", b">B<")
        self.assertEqual(_preserve_unchanged_feed(changed, original), changed)
        self.assertEqual(_preserve_unchanged_feed(changed, b"not XML"), changed)

    def test_registry_has_unique_output_paths(self):
        registry = load_feed_registry()
        paths = [config.output_name or name for name, config in registry.items()]
        self.assertEqual(len(paths), len(set(paths)))
