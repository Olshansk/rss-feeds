"""Transactional checkpoints, observation history, and evidence in SQLite."""

import fcntl
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


class Store:
    """Keep runtime evidence outside Git while retaining every observation."""

    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(path, timeout=30)
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS records (
                kind TEXT NOT NULL, key TEXT NOT NULL, payload TEXT NOT NULL,
                PRIMARY KEY (kind, key)
            );
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY, observed_at TEXT NOT NULL,
                task TEXT NOT NULL, payload TEXT NOT NULL
            );
        """)

    @contextmanager
    def transaction(self):
        """Commit the complete observation or roll back all its write paths."""
        with self.connection:
            yield self

    def get(self, kind, key, default=None):
        row = self.connection.execute("SELECT payload FROM records WHERE kind=? AND key=?", (kind, str(key))).fetchone()
        return json.loads(row[0]) if row else default

    def put(self, kind, key, value):
        self.connection.execute("INSERT OR REPLACE INTO records VALUES (?, ?, ?)", (kind, str(key), json.dumps(value)))

    def values(self, kind):
        return [
            json.loads(row[0]) for row in self.connection.execute("SELECT payload FROM records WHERE kind=?", (kind,))
        ]

    def record(self, task, value, now=None):
        self.connection.execute(
            "INSERT INTO observations(observed_at,task,payload) VALUES (?,?,?)",
            (now or datetime.now(UTC).isoformat(), task, json.dumps(value)),
        )

    def close(self):
        self.connection.close()


def import_legacy(store, path):
    """Import the existing checkpoint once, preserving history without certifying it.

    How:
    1. Refuse to overwrite an initialized database.
    2. Import checkpoint/run metadata in one transaction.
    3. Preserve available raw logs; the auditor re-fetches post-repair evidence.
    """
    if store.get("state", "ci") is not None:
        raise ValueError("Database already initialized; refusing to overwrite its checkpoint")
    path = Path(path)
    state = json.loads(path.read_text())
    runs_path = path.with_name("runs.json")
    with store.transaction():
        store.put("state", "ci", state)
        for run in json.loads(runs_path.read_text()) if runs_path.exists() else []:
            store.put("run", run["id"], run)
        for record in state.get("verified_runs", []):
            store.put("legacy_verified", record["id"], record)
        evidence_dir = Path(state.get("evidence_dir", str(path.parent)))
        for log in evidence_dir.glob("*.log"):
            store.put("legacy_log", log.name, log.read_text())
        store.record(
            "import",
            {
                "source": str(path),
                "clean_since": state.get("clean_since"),
                "note": "Imported evidence is historical; a fresh audit is still required.",
            },
        )


@contextmanager
def task_lock(database):
    """Allow only one task writer per database; release on exit or process death."""
    path = Path(str(database) + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Another scheduled task is using this database") from error
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)
