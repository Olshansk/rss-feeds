"""Regression tests for persisted audits and false clean-window prevention."""

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

from scheduled_tasks.ci import audit, check_prs, refresh_evidence, window_status
from scheduled_tasks.github import GitHub
from scheduled_tasks.storage import Store, import_legacy

START = datetime(2026, 10, 10, 0, 0, tzinfo=UTC)
REGISTRY = {
    "http": SimpleNamespace(enabled=True, type="requests"),
    "browser": SimpleNamespace(enabled=True, type="selenium"),
    "paused": SimpleNamespace(enabled=False, type="selenium"),
}


def run(number=1, attempt=1, conclusion="success", name="Run Feeds"):
    return {
        "id": number,
        "run_attempt": attempt,
        "name": name,
        "event": "schedule",
        "head_branch": "main",
        "head_sha": "abc",
        "created_at": (START + timedelta(minutes=2)).isoformat(),
        "updated_at": (START + timedelta(minutes=5)).isoformat(),
        "status": "completed",
        "conclusion": conclusion,
    }


def state():
    return {
        "query_interval_start": START.isoformat(),
        "repair_pushed_at": START.isoformat(),
        "last_checked_at": START.isoformat(),
        "last_repair_sha": "abc",
        "clean_since": START.isoformat(),
    }


def client(runs):
    github = Mock()
    github.runs.return_value = runs
    github.open_prs.return_value = []
    github.api.side_effect = lambda path: (
        {"sha": "abc"} if path == "commits/main" else {"status": "identical", "files": []}
    )

    def pages(path):
        if path.startswith("actions/workflows"):
            return [
                {
                    "workflows": [
                        {"name": name, "state": "active"}
                        for name in ("Run Feeds", "Run Selenium Feeds", "Test Feed Generation")
                    ]
                }
            ]
        return [{"jobs": [{"conclusion": "success", "steps": [{"conclusion": "success"}]}]}]

    github.pages.side_effect = pages
    github.log.return_value = "Successfully ran: http\nFailed: 0\n"
    return github


class StoreTests(unittest.TestCase):
    def test_rollback_keeps_all_write_paths_consistent(self):
        store = Store(":memory:")
        with self.assertRaises(RuntimeError), store.transaction():
            store.put("state", "ci", state())
            store.record("ci", {"success": True})
            raise RuntimeError("interrupt")
        self.assertIsNone(store.get("state", "ci"))
        self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM observations").fetchone()[0], 0)
        store.close()

    def test_import_preserves_window_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps(state()))
            path.with_name("runs.json").write_text(json.dumps([run()]))
            store = Store(":memory:")
            import_legacy(store, path)
            self.assertEqual(store.get("state", "ci")["clean_since"], START.isoformat())
            self.assertEqual(store.get("run", 1)["id"], 1)
            with self.assertRaises(ValueError):
                import_legacy(store, path)
            store.close()


class CoverageTests(unittest.TestCase):
    def test_exact_feed_set_and_zero_failures_required(self):
        for log in (
            "Successfully ran: http\n",
            "Successfully ran: paused\nFailed: 0",
            "Successfully ran: http\nFailed: 0\nTraceback (most recent call last):",
        ):
            with self.subTest(log=log), self.assertRaises(ValueError):
                refresh_evidence(run(), log, {"http"})
        self.assertEqual(refresh_evidence(run(), "Successfully ran: http\nFailed: 0", {"http"})["feeds"], ["http"])

    def test_no_runs_or_manual_runs_cannot_complete(self):
        for records in ([], [{"type": "requests", "scheduled": False, "created_at": START.isoformat()}]):
            result = window_status(state(), records, START + timedelta(hours=10))
            self.assertFalse(result["eligible"])
            self.assertTrue(result["missing_slots"])

    def test_hourly_coverage_and_no_pending_required(self):
        records = [
            {"type": kind, "scheduled": True, "created_at": (START + timedelta(hours=hour, minutes=minute)).isoformat()}
            for kind, minute in (("requests", 5), ("selenium", 35))
            for hour in range(11)
        ]
        result = window_status(state(), records, START + timedelta(hours=10, minutes=10))
        self.assertTrue(result["eligible"])
        result = window_status({**state(), "pending_runs": [99]}, records, START + timedelta(hours=10, minutes=10))
        self.assertFalse(result["eligible"])
        records.pop(3)
        self.assertFalse(window_status(state(), records, START + timedelta(hours=10, minutes=10))["eligible"])

    def test_pr_absent_pending_and_failed_checks_are_distinct(self):
        prs = [
            {"number": 1, "headRefOid": "a", "statusCheckRollup": []},
            {"number": 2, "headRefOid": "b", "statusCheckRollup": [{"status": "IN_PROGRESS", "conclusion": None}]},
            {"number": 3, "headRefOid": "c", "statusCheckRollup": [{"state": "ERROR"}]},
        ]
        failed, pending, unchecked = check_prs(prs)
        self.assertEqual([p["pr"] for p in failed], [3])
        self.assertEqual([p["pr"] for p in pending], [2])
        self.assertEqual(unchecked, [1])


class AuditFixture(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        with self.store.transaction():
            self.store.put("state", "ci", state())

    def tearDown(self):
        self.store.close()


class AuditTests(AuditFixture):
    def test_successful_rerun_does_not_hide_failed_attempt(self):
        github = client([run(attempt=2)])
        github.attempt.return_value = run(conclusion="failure")
        result = audit(self.store, github, START + timedelta(minutes=10), REGISTRY)
        self.assertEqual(result["new_errors"][0]["attempt"], 1)
        self.assertIsNone(self.store.get("state", "ci")["clean_since"])
        self.assertTrue(self.store.get("state", "ci")["needs_repair"])
        self.assertIsNotNone(self.store.get("log", "1:1"))
        # The same historical failure must not repeatedly appear as new.
        self.assertFalse(audit(self.store, github, START + timedelta(minutes=20), REGISTRY)["new_errors"])

    def test_green_job_with_failed_step_resets_timer(self):
        github = client([run()])
        pages = github.pages.side_effect
        github.pages.side_effect = lambda path: (
            pages(path)
            if path.startswith("actions/workflows")
            else [{"jobs": [{"conclusion": "success", "steps": [{"conclusion": "failure"}]}]}]
        )
        self.assertTrue(audit(self.store, github, START + timedelta(minutes=10), REGISTRY)["new_errors"])
        self.assertIsNone(self.store.get("state", "ci")["clean_since"])

    def test_api_failure_does_not_advance_checkpoint(self):
        github = client([run()])
        github.log.side_effect = RuntimeError("unavailable")
        with self.assertRaises(RuntimeError):
            audit(self.store, github, START + timedelta(minutes=10), REGISTRY)
        self.assertEqual(self.store.get("state", "ci"), state())
        self.assertIsNone(self.store.get("run", 1))

    def test_pending_run_is_rechecked_after_completion(self):
        pending = {**run(), "status": "in_progress", "conclusion": None}
        github = client([pending])
        self.assertEqual(audit(self.store, github, START + timedelta(minutes=10), REGISTRY)["pending_runs"], [1])
        github.runs.return_value = [run()]
        result = audit(self.store, github, START + timedelta(minutes=20), REGISTRY)
        self.assertEqual(result["pending_runs"], [])
        self.assertEqual(result["verified_attempts"], ["1:1"])

    def test_monitoring_gap_invalidates_old_window(self):
        result = audit(self.store, client([]), START + timedelta(minutes=31), REGISTRY)
        self.assertFalse(result["eligible"])
        self.assertIsNone(self.store.get("state", "ci")["clean_since"])


class PaginationTests(unittest.TestCase):
    def test_cap_splits_interval_and_deduplicates_boundaries(self):
        github = GitHub()
        calls = []

        def pages(path):
            interval = parse_qs(urlsplit(path).query)["created"][0]
            calls.append(interval)
            if len(calls) == 1:
                return [{"total_count": 1000, "workflow_runs": []}]
            return [{"total_count": 1, "workflow_runs": [{"id": 1}]}]

        github.pages = pages
        self.assertEqual(github.runs(START.isoformat(), (START + timedelta(hours=1)).isoformat()), [{"id": 1}])
        self.assertEqual(len(calls), 3)

    def test_all_pages_are_included(self):
        github = GitHub()
        github.pages = Mock(return_value=[{"workflow_runs": [{"id": 1}]}, {"workflow_runs": [{"id": 2}]}])
        self.assertEqual({r["id"] for r in github.runs(START.isoformat(), START.isoformat())}, {1, 2})

    def test_unsplittable_cap_fails_closed(self):
        github = GitHub()
        github.pages = Mock(return_value=[{"total_count": 1000, "workflow_runs": []}])
        with self.assertRaises(ValueError):
            github.runs(START.isoformat(), START.isoformat())


class ContentTests(unittest.TestCase):
    def test_independent_sample_detects_missing_and_changed_entries(self):
        from scheduled_tasks.content import compare

        snapshot = {
            "source_url": "https://example.com/blog",
            "captured_at": START.isoformat(),
            "method": "browser extraction",
            "items": [
                {"link": "https://example.com/one", "title": "Correct title"},
                {"link": "https://example.com/two", "title": "Missing item"},
                {
                    "link": "https://example.com/future",
                    "title": "Future item",
                    "published_at": (START + timedelta(days=1)).isoformat(),
                },
            ],
        }
        xml = (
            "<rss><channel><item><link>https://example.com/one</link><title>Wrong title</title></item></channel></rss>"
        )
        result = compare(snapshot, xml, START)
        self.assertFalse(result["matches"])
        self.assertEqual([d["field"] for d in result["discrepancies"]], ["title", "item"])
        self.assertEqual(result["deferred"], ["https://example.com/future"])
        with self.assertRaises(ValueError):
            compare(snapshot, xml, START + timedelta(hours=1))

    def test_historical_items_do_not_make_incremental_sample_fail(self):
        from scheduled_tasks.content import compare

        snapshot = {
            "source_url": "https://example.com/blog",
            "captured_at": START.isoformat(),
            "method": "public source API",
            "items": [{"link": "https://example.com/one", "title": "A & B"}],
        }
        xml = "<rss><channel><item><link>https://example.com/one</link><title>A &amp; B</title></item><item><link>https://example.com/old</link><title>Old</title></item></channel></rss>"
        self.assertTrue(compare(snapshot, xml, START)["matches"])


class LockTests(unittest.TestCase):
    def test_overlapping_task_is_rejected_and_lock_is_released(self):
        from scheduled_tasks.storage import task_lock

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tasks.sqlite3"
            with task_lock(path), self.assertRaises(RuntimeError), task_lock(path):
                pass
            with task_lock(path):
                pass


class AdditionalAuditTests(AuditFixture):
    def test_skipped_run_evidence_issue_survives_next_audit(self):
        github = client([run(conclusion="skipped", name="Other checks")])
        first = audit(self.store, github, START + timedelta(minutes=10), REGISTRY)
        second = audit(self.store, github, START + timedelta(minutes=20), REGISTRY)
        self.assertTrue(first["issues"])
        self.assertEqual(first["issues"], second["issues"])

    def test_deleted_run_is_not_silently_hidden(self):
        with self.store.transaction():
            self.store.put("run", 1, run())
        result = audit(self.store, client([]), START + timedelta(minutes=10), REGISTRY)
        self.assertIn("missing from GitHub inventory", result["issues"][0])

    def test_post_repair_window_requires_both_scheduled_types_and_offline_checks(self):
        with self.store.transaction():
            current = state()
            current["clean_since"] = None
            self.store.put("state", "ci", current)
        browser = run(number=2, name="Run Selenium Feeds")
        offline = {**run(number=3, name="Test Feed Generation"), "event": "push"}
        github = client([run(), browser, offline])
        github.log.side_effect = lambda number, attempt: (
            "Successfully ran: browser\nFailed: 0" if number == 2 else "Successfully ran: http\nFailed: 0"
        )
        result = audit(self.store, github, START + timedelta(minutes=10), REGISTRY)
        self.assertFalse(result["eligible"])
        self.assertEqual(self.store.get("state", "ci")["clean_since"], browser["updated_at"])


class EventTests(unittest.TestCase):
    def test_new_events_are_deduplicated_and_lost_boundary_is_reported(self):
        from scheduled_tasks.events import audit_events

        store = Store(":memory:")
        github = Mock()
        github.pages.return_value = [[{"id": "1", "type": "PushEvent", "created_at": START.isoformat()}]]
        self.assertTrue(audit_events(store, github)["initial_inventory"])
        self.assertEqual(audit_events(store, github)["new_events"], [])
        github.pages.return_value = [[{"id": "3", "type": "PullRequestEvent", "created_at": START.isoformat()}]]
        result = audit_events(store, github)
        self.assertTrue(result["coverage_gap"])
        self.assertEqual(result["new_events"][0]["id"], "3")
        store.close()


class HistoricalRerunTests(AuditFixture):
    def test_old_pr_creation_date_does_not_hide_new_failed_attempt(self):
        old_created = (START - timedelta(days=20)).isoformat()
        current = {**run(attempt=2, name="Test Feed Generation"), "created_at": old_created, "event": "pull_request"}
        github = client([current])
        github.attempt.return_value = {**run(conclusion="failure"), "created_at": old_created}
        result = audit(self.store, github, START + timedelta(minutes=10), REGISTRY)
        requested_start = datetime.fromisoformat(github.runs.call_args.args[0])
        self.assertLessEqual(requested_start, START - timedelta(days=30))
        self.assertEqual(result["new_errors"][0]["attempt"], 1)
        self.assertIsNone(self.store.get("state", "ci")["clean_since"])

    def test_expanding_history_does_not_reset_for_pre_repair_failure(self):
        old = {
            **run(conclusion="failure"),
            "created_at": (START - timedelta(days=20)).isoformat(),
            "updated_at": (START - timedelta(days=19)).isoformat(),
        }
        github = client([old])
        result = audit(self.store, github, START + timedelta(minutes=10), REGISTRY)
        self.assertEqual(result["new_errors"], [])
        self.assertEqual(self.store.get("state", "ci")["clean_since"], START.isoformat())
        github.log.assert_not_called()
        self.assertIsNotNone(self.store.get("run", 1))

    def test_pre_repair_attempt_of_current_rerun_is_not_a_new_failure(self):
        current = {
            **run(attempt=2, name="Test Feed Generation"),
            "created_at": (START - timedelta(days=20)).isoformat(),
        }
        github = client([current])
        github.attempt.return_value = {
            **run(conclusion="failure"),
            "updated_at": (START - timedelta(days=10)).isoformat(),
        }
        result = audit(self.store, github, START + timedelta(minutes=10), REGISTRY)
        self.assertEqual(result["new_errors"], [])
        self.assertIsNotNone(self.store.get("attempt", "1:1"))
        self.assertIsNone(self.store.get("log", "1:1"))
        self.assertEqual(github.log.call_count, 1)
