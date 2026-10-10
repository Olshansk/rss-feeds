"""Scheduled source entries must not break refreshes or publish early."""

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock, patch
from xml.etree import ElementTree as ET

from lxml import etree

from models import FeedConfig
from run_all_feeds import run_feed
from utils import save_rss_feed
from validate_feeds import validate_xml

PAST = "<item><title>Published</title><link>https://example.com/past</link><guid>past-id</guid><pubDate>Thu, 01 Oct 2026 00:00:00 GMT</pubDate></item>"
SCHEDULED = "<item><title>Wie IBM mit KI 4,5 Milliarden Dollar einsparte</title><link>https://ai-first.ai/podcast/wie-ibm-mit-ki-4-5-milliarden-dollar-einsparte</link><guid>scheduled-id</guid><pubDate>Fri, 16 Oct 2026 02:00:00 +0200</pubDate></item>"


def generator(items):
    xml = etree.tostring(etree.fromstring(f"<rss><channel>{items}</channel></rss>".encode()), pretty_print=True)
    return Mock(rss_str=Mock(return_value=xml))


class ScheduledPublicationTests(unittest.TestCase):
    def test_publication_boundary_preserves_source_dates_and_identity(self):
        fg = generator(PAST + SCHEDULED)
        source = fg.rss_str()
        with tempfile.TemporaryDirectory() as tmp, patch("utils.get_feeds_dir", return_value=Path(tmp)):
            with patch("utils.datetime") as clock, self.assertLogs("utils", level="INFO") as logs:
                clock.now.return_value = datetime(2026, 10, 15, 23, 59, 59, tzinfo=UTC)
                path = save_rss_feed(fg, "example")
            self.assertIn("Scheduled entry deferred:", "\n".join(logs.output))
            self.assertEqual(len(ET.fromstring(path.read_bytes()).findall("channel/item")), 1)
            # The strict validator remains unchanged; freeze its clock at publication too.
            with patch("utils.datetime") as clock, patch("validate_feeds.datetime") as validation_clock:
                clock.now.return_value = datetime(2026, 10, 16, tzinfo=UTC)
                validation_clock.now.return_value = clock.now.return_value
                save_rss_feed(fg, "example")
            items = ET.fromstring(path.read_bytes()).findall("channel/item")
            self.assertEqual([item.findtext("guid") for item in items], ["scheduled-id", "past-id"])
            self.assertEqual(items[0].findtext("pubDate"), "Fri, 16 Oct 2026 02:00:00 +0200")
            self.assertEqual(fg.rss_str(), source)

    def test_future_only_and_malformed_entries_preserve_last_good_xml(self):
        with tempfile.TemporaryDirectory() as tmp, patch("utils.get_feeds_dir", return_value=Path(tmp)):
            path = save_rss_feed(generator(PAST), "example")
            original = path.read_bytes()
            for items in (
                SCHEDULED,
                PAST + SCHEDULED.replace("Fri, 16 Oct 2026 02:00:00 +0200", "invalid"),
                PAST + SCHEDULED.replace("<title>Wie IBM mit KI 4,5 Milliarden Dollar einsparte</title>", ""),
            ):
                with self.subTest(items=items), patch("utils.datetime") as clock:
                    clock.now.return_value = datetime(2026, 10, 10, tzinfo=UTC)
                    with self.assertRaises(ValueError):
                        save_rss_feed(generator(items), "example")
                self.assertEqual(path.read_bytes(), original)
                self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_future_duplicate_does_not_displace_published_entry(self):
        future = SCHEDULED.replace("scheduled-id", "past-id")
        with tempfile.TemporaryDirectory() as tmp, patch("utils.get_feeds_dir", return_value=Path(tmp)):
            with patch("utils.datetime") as clock:
                clock.now.return_value = datetime(2026, 10, 10, tzinfo=UTC)
                path = save_rss_feed(generator(PAST + future), "example")
            self.assertEqual(ET.fromstring(path.read_bytes()).findtext("channel/item/title"), "Published")

    def test_runner_surfaces_deferrals_in_log_and_summary(self):
        config = FeedConfig(script="ollama_blog.py", type="requests", blog_url="https://example.com")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "summary.md"

            def refresh(*args, **kwargs):
                (root / "feed_example.xml").write_bytes(generator(PAST).rss_str())
                return Mock(
                    returncode=0,
                    stdout="",
                    stderr="INFO - Scheduled entry deferred: example: Upcoming until 2026-10-16T00:00:00+00:00\n",
                )

            with (
                patch("run_all_feeds.get_feeds_dir", return_value=root),
                patch("run_all_feeds.subprocess.run", side_effect=refresh),
                patch.dict("os.environ", {"GITHUB_STEP_SUMMARY": str(summary)}),
                self.assertLogs("run_all_feeds", level="INFO") as logs,
            ):
                self.assertTrue(run_feed("example", config))
            self.assertIn("1 scheduled entries deferred", summary.read_text())
            self.assertIn("Upcoming until", "\n".join(logs.output))

    def test_direct_validation_still_rejects_future_dates(self):
        with patch("validate_feeds.datetime") as clock:
            clock.now.return_value = datetime(2026, 10, 10, tzinfo=UTC)
            self.assertEqual(validate_xml(generator(PAST + SCHEDULED).rss_str())["status"], "ERROR")
