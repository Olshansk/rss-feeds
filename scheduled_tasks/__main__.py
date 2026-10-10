"""Run repository-owned tasks without an extra scheduler or service."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from scheduled_tasks.ci import audit
from scheduled_tasks.content import compare
from scheduled_tasks.events import audit_events
from scheduled_tasks.github import GitHub
from scheduled_tasks.storage import Store, import_legacy, task_lock

ROOT = Path(__file__).resolve().parents[1]


def main():
    """Dispatch one bounded task and retain failures for the next invocation.

    How:
    1. Open the local evidence database and parse the selected task.
    2. Import history, record a repair, or execute one read-only GitHub audit.
    3. Save exceptions without advancing a successful checkpoint; return nonzero.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / ".cache/scheduled_tasks/tasks.sqlite3")
    parser.add_argument("--repository", default="Olshansk/rss-feeds")
    commands = parser.add_subparsers(dest="task", required=True)
    importer = commands.add_parser("import-history")
    importer.add_argument("path", type=Path)
    repair = commands.add_parser("repair")
    repair.add_argument("--sha", required=True)
    repair.add_argument("--reason", required=True)
    content = commands.add_parser("compare-content")
    content.add_argument("--snapshot", type=Path, required=True)
    content.add_argument("--xml", type=Path, required=True)
    commands.add_parser("ci")
    commands.add_parser("prs")
    commands.add_parser("events")
    commands.add_parser("status")
    args = parser.parse_args()
    try:
        with task_lock(args.database):
            return execute(args)
    except RuntimeError as error:
        print(json.dumps({"error": str(error)}))
        return 2


def execute(args):
    """Execute the selected task while the caller holds the database lock."""
    store = Store(args.database)
    github = GitHub(args.repository)
    result, code = None, 0
    try:
        if args.task == "import-history":
            import_legacy(store, args.path)
            result = {"imported": str(args.path)}
        elif args.task == "repair":
            commit = github.api(f"commits/{args.sha}")
            now = datetime.now(UTC).isoformat()
            with store.transaction():
                state = store.get("state", "ci", {})
                state.update(
                    last_repair_sha=commit["sha"],
                    repair_pushed_at=now,
                    clean_since=None,
                    needs_repair=False,
                    earliest_completion_at=None,
                    monitoring_status="awaiting post-repair checks",
                )
                state.setdefault("query_interval_start", now)
                state.setdefault("repairs", []).append(
                    {"sha": commit["sha"], "reason": args.reason, "recorded_at": now}
                )
                store.put("state", "ci", state)
                store.record("repair", state["repairs"][-1])
            result = {"repair": commit["sha"], "clean_since": None}
        elif args.task == "compare-content":
            snapshot = json.loads(args.snapshot.read_text())
            xml = args.xml.read_text()
            result = compare(snapshot, xml)
            with store.transaction():
                store.record("content", {"snapshot": snapshot, "xml_path": str(args.xml), "xml": xml, "result": result})
            code = int(not result["matches"])
        elif args.task == "ci":
            result = audit(store, github)
            code = int(
                bool(result["needs_repair"] or result["new_errors"] or result["issues"] or result["missing_slots"])
            )
        elif args.task == "events":
            result = audit_events(store, github)
            code = int(result["coverage_gap"])
        elif args.task == "prs":
            result = github.open_prs()
            with store.transaction():
                store.put("state", "prs", result)
                store.record("prs", result)
        else:
            result = store.get("state", "ci", {})
    except Exception as error:
        with store.transaction():
            store.record("exception", {"task": args.task, "type": type(error).__name__, "message": str(error)})
        result, code = {"error": str(error), "task": args.task}, 2
    finally:
        store.close()
    print(json.dumps(result, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
