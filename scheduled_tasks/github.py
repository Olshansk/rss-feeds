"""Small GitHub CLI adapter with explicit pagination and attempt-aware logs."""

import json
import subprocess
from datetime import datetime, timedelta
from io import BytesIO
from urllib.parse import urlencode
from zipfile import ZipFile


class GitHub:
    def __init__(self, repository="Olshansk/rss-feeds"):
        self.repository = repository

    def command(self, *arguments):
        """Execute bounded CLI calls without a shell; propagate failures."""
        return subprocess.check_output(["gh", *map(str, arguments)], text=True, timeout=120)

    def api(self, path):
        return json.loads(self.command("api", f"repos/{self.repository}/{path}"))

    def pages(self, path):
        return json.loads(self.command("api", "--paginate", "--slurp", f"repos/{self.repository}/{path}"))

    def runs(self, start, end):
        """List the complete time interval, splitting GitHub's capped searches.

        How:
        1. Request all pages without restricting event, branch, or conclusion.
        2. Split intervals that reach the API's 1,000-result filtered-search cap.
        3. Deduplicate inclusive boundaries and fail if a one-second slice is capped.
        """
        query = urlencode({"per_page": 100, "created": f"{start}..{end}"})
        pages = self.pages(f"actions/runs?{query}")
        if any(page.get("total_count", 0) >= 1000 for page in pages):
            first, last = (datetime.fromisoformat(value.replace("Z", "+00:00")) for value in (start, end))
            if last - first <= timedelta(seconds=1):
                raise ValueError("GitHub run search is capped even at one second; coverage is incomplete")
            middle = (first + (last - first) / 2).replace(microsecond=0).isoformat()
            combined = self.runs(start, middle) + self.runs(middle, end)
        else:
            combined = [run for page in pages for run in page["workflow_runs"]]
        return list({run["id"]: run for run in combined}.values())

    def attempt(self, run_id, attempt):
        return self.api(f"actions/runs/{run_id}/attempts/{attempt}")

    def pending_runs(self):
        """Discover unfinished runs even when their creation predates the audit window.

        How:
        1. Paginate every unfinished status without a creation-date restriction.
        2. Fail closed if GitHub's filtered-search cap prevents complete coverage.
        3. Deduplicate runs that change status between requests.
        """
        runs = {}
        for status in ("in_progress", "queued", "waiting", "pending", "requested"):
            pages = self.pages(f"actions/runs?status={status}&per_page=100")
            if any(page.get("total_count", 0) >= 1000 for page in pages):
                raise ValueError(f"GitHub {status} run search is capped; pending coverage is incomplete")
            runs.update((run["id"], run) for page in pages for run in page["workflow_runs"])
        return list(runs.values())

    def log(self, run_id, attempt):
        """Read full job logs independently of incomplete GitHub step metadata.

        How:
        1. Download the exact attempt archive as bytes, without CLI step filtering.
        2. Read each top-level job transcript once, excluding duplicate per-step logs.
        3. Reject empty or invalid archives so missing evidence cannot pass silently.
        """
        archive = subprocess.check_output(
            ["gh", "api", f"repos/{self.repository}/actions/runs/{run_id}/attempts/{attempt}/logs"],
            timeout=120,
        )
        with ZipFile(BytesIO(archive)) as logs:
            transcripts = [
                logs.read(name).decode("utf-8") for name in logs.namelist() if "/" not in name and name.endswith(".txt")
            ]
        if not transcripts or not any(text.strip() for text in transcripts):
            raise ValueError(f"Attempt {run_id}:{attempt} log archive has no job transcripts")
        return "\n".join(transcripts)

    def open_prs(self):
        """Paginate open PRs, then inspect current head checks and review decisions.

        How:
        1. Enumerate all open PR numbers through the paginated REST endpoint.
        2. Fetch merge eligibility and check rollups for each current head.
        3. Return exact SHAs so reviews and future merges can detect races.
        """
        numbers = [pr["number"] for page in self.pages("pulls?state=open&per_page=100") for pr in page]
        fields = (
            "number,title,url,headRefOid,baseRefName,isDraft,author,reviewDecision,mergeStateStatus,statusCheckRollup"
        )
        return [
            json.loads(self.command("pr", "view", number, "--repo", self.repository, "--json", fields))
            for number in numbers
        ]
