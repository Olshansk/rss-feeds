"""Small GitHub CLI adapter with explicit pagination and attempt-aware logs."""

import json
import subprocess
from datetime import datetime, timedelta
from urllib.parse import urlencode


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

    def log(self, run_id, attempt):
        return self.command("run", "view", run_id, "--repo", self.repository, "--attempt", attempt, "--log")

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
