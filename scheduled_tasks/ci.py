"""One-shot CI audits; completion requires evidence, never just elapsed time."""

import re
from datetime import UTC, datetime, timedelta

from feed_generators.models import load_feed_registry

REFRESHES = {"Run Feeds": "requests", "Run Selenium Feeds": "selenium"}
ERRORS = {"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale"}


def timestamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def refresh_evidence(run, log, expected):
    """Require exact enabled-feed coverage and explicit zero failures."""
    if not expected:
        raise ValueError("Empty enabled-feed scope cannot prove a successful refresh")
    actual = set(re.findall(r"Successfully ran: (\S+)", log))
    if actual != set(expected) or not re.search(r"Failed: 0\b", log):
        raise ValueError(f"Incomplete feed coverage in {run['id']}: expected {sorted(expected)}, got {sorted(actual)}")
    if any(marker in log for marker in ("Traceback", "Error running", "##[error]")):
        raise ValueError(f"Error in refresh log {run['id']}")
    return {
        "id": run["id"],
        "attempt": run["run_attempt"],
        "type": REFRESHES[run["name"]],
        "created_at": run["created_at"],
        "completed_at": run["updated_at"],
        "scheduled": run["event"] == "schedule" and run["head_branch"] == "main",
        "head_sha": run["head_sha"],
        "feeds": sorted(actual),
    }


def check_prs(prs):
    """Distinguish failing, pending, and absent checks on current PR heads."""
    failures, pending, unchecked = [], [], []
    for pr in prs:
        checks = pr["statusCheckRollup"] or []
        if not checks:
            unchecked.append(pr["number"])
        for check in checks:
            status = check.get("conclusion") if check.get("status") == "COMPLETED" else check.get("state")
            if status and status.lower() in ERRORS | {"error"}:
                failures.append({"pr": pr["number"], "sha": pr["headRefOid"], "check": check})
            elif status not in ("SUCCESS", "SKIPPED", "NEUTRAL"):
                pending.append({"pr": pr["number"], "check": check})
    return failures, pending, unchecked


def window_status(state, records, now):
    """Verify hourly scheduled slots, elapsed time, and a settled final inventory.

    How:
    1. Require a post-repair candidate start and ten elapsed hours.
    2. Match each elapsed hourly schedule slot to a successful scheduled refresh.
    3. Reject pending work, disabled workflows, and incomplete audit evidence.
    """
    start = state.get("clean_since")
    if not start:
        return {"eligible": False, "clean_hours": 0, "missing_slots": []}
    start = timestamp(start)
    missing = []
    # Schedules are hourly at :00 (HTTP) and :30 (Selenium). A delayed run may
    # satisfy its preceding slot, but one run cannot satisfy two slots.
    for kind, minute in (("requests", 0), ("selenium", 30)):
        available = sorted(timestamp(r["created_at"]) for r in records if r["type"] == kind and r["scheduled"])
        slot = start.replace(minute=minute, second=0, microsecond=0)
        if slot <= start:
            slot += timedelta(hours=1)
        while slot <= now:
            match = next((value for value in available if slot <= value < slot + timedelta(hours=1)), None)
            if match is None:
                missing.append(f"{kind}:{slot.isoformat()}")
            else:
                available.remove(match)
            slot += timedelta(hours=1)
    hours = (now - start).total_seconds() / 3600
    eligible = (
        hours >= state.get("required_clean_hours", 10)
        and not missing
        and not state.get("pending_runs")
        and not state.get("pending_pr_checks")
        and not state.get("audit_issues")
    )
    return {"eligible": eligible, "clean_hours": round(hours, 2), "missing_slots": missing}


def audit(store, github, now=None, registry=None):
    """Collect fresh metadata and exact attempts, then atomically checkpoint evidence.

    How:
    1. Paginate all events/branches since the original audit boundary and recheck PR heads.
    2. Inspect newly changed attempts, their jobs/steps, and full refresh logs.
    3. Reset the timer for new errors; require a recorded repair before restarting it.
    4. Validate coverage and persist metadata, logs, and the observation together.
    """
    now = now or datetime.now(UTC)
    state = store.get("state", "ci")
    if not state:
        raise ValueError("Import the existing checkpoint or initialize with the repair command first")
    registry = registry or load_feed_registry()
    runs = github.runs(state["query_interval_start"], now.isoformat())
    # Recheck pending work even if it predates the original search boundary.
    ids = {r["id"] for r in runs}
    for old in store.values("run"):
        if old["status"] != "completed" and old["id"] not in ids:
            runs.append(github.api(f"actions/runs/{old['id']}"))
    prs = github.open_prs()
    failures, pending_prs, unchecked = check_prs(prs)
    workflows = [w for page in github.pages("actions/workflows?per_page=100") for w in page["workflows"]]
    issues = [
        f"{name} workflow absent or disabled"
        for name in (*REFRESHES, "Test Feed Generation")
        if not any(w["name"] == name and w["state"] == "active" for w in workflows)
    ]
    missing_runs = [
        r["id"]
        for r in store.values("run")
        if timestamp(r["created_at"]) >= timestamp(state["query_interval_start"]) and r["id"] not in ids
    ]
    if missing_runs:
        issues.append(f"Previously observed runs missing from GitHub inventory: {missing_runs}")
    evidence, inspected, logs = [], [], {}
    assessments = {}
    if state.get("last_checked_at") and now - timestamp(state["last_checked_at"]) > timedelta(minutes=30):
        state["previous_clean_since"] = state.get("clean_since")
        state["clean_since"] = None
        state["coverage_restart_at"] = now.isoformat()
    head = github.api("commits/main")["sha"]
    comparison = github.api(f"compare/{state['last_repair_sha']}...{head}")
    if (
        comparison["status"] not in ("ahead", "identical")
        or len(comparison.get("files", [])) >= 300
        or any(
            not (f["filename"].startswith("feeds/") and f["filename"].endswith(".xml"))
            for f in comparison.get("files", [])
        )
    ):
        issues.append("Main source changed since recorded repair; review and record the new baseline")
    repair_at = timestamp(state["repair_pushed_at"])
    coverage_at = max(repair_at, timestamp(state.get("coverage_restart_at", state["repair_pushed_at"])))
    for run in runs:
        old = store.get("run", run["id"])
        changed = not old or any(
            old.get(k) != run.get(k) for k in ("status", "conclusion", "run_attempt", "updated_at")
        )
        for number in range(1, run["run_attempt"] + 1):
            key = f"{run['id']}:{number}"
            previous = store.get("attempt", key)
            if previous and (number < run["run_attempt"] or not changed):
                if timestamp(previous["updated_at"]) >= repair_at:
                    issues.extend(store.get("attempt_issue", key, []))
                continue
            # Imported pre-repair attempts were already reviewed. Changed reruns
            # are still inspected, including a failed earlier attempt.
            if not changed and timestamp(run["updated_at"]) < repair_at:
                continue
            attempt = run if number == run["run_attempt"] else github.attempt(run["id"], number)
            if attempt["status"] != "completed":
                continue
            jobs = [
                job
                for page in github.pages(f"actions/runs/{run['id']}/attempts/{number}/jobs?per_page=100")
                for job in page["jobs"]
            ]
            bad = [
                job
                for job in jobs
                if job.get("conclusion") in ERRORS or any(s.get("conclusion") in ERRORS for s in job.get("steps", []))
            ]
            problem = attempt["conclusion"] in ERRORS or bool(bad)
            if problem:
                failures.append({"id": run["id"], "attempt": number, "at": attempt["updated_at"], "jobs": bad})
            assessments[key] = []
            if (
                not jobs
                or not any(j.get("conclusion") == "success" for j in jobs)
                or attempt["conclusion"] not in {"success"} | ERRORS
            ):
                assessments[key].append(f"Run {key} lacks successful job evidence")
                issues.extend(assessments[key])
            log = github.log(run["id"], number)
            logs[key] = log
            inspected.append((key, attempt))
            if (
                attempt["conclusion"] == "success"
                and run["name"] in REFRESHES
                and timestamp(run["created_at"]) >= repair_at
            ):
                expected = {
                    name for name, cfg in registry.items() if cfg.enabled and cfg.type == REFRESHES[run["name"]]
                }
                try:
                    record = refresh_evidence(attempt, log, expected)
                    evidence.append((key, record))
                except ValueError as error:
                    failures.append(
                        {"id": run["id"], "attempt": number, "at": attempt["updated_at"], "error": str(error)}
                    )
    with store.transaction():
        new_failures = []
        for failure in failures:
            key = str(failure)
            if store.get("failure", key) is None:
                store.put("failure", key, failure)
                new_failures.append(failure)
        if new_failures:
            state["previous_clean_since"] = state.get("clean_since")
            state["clean_since"] = None
            state["last_error_observed_at"] = now.isoformat()
            state["last_error_at"] = max(timestamp(f.get("at", now.isoformat())) for f in new_failures).isoformat()
            state["needs_repair"] = True
        for key, attempt in inspected:
            store.put("attempt", key, attempt)
            store.put("attempt_issue", key, assessments[key])
            store.put("log", key, logs[key])
        for key, record in evidence:
            store.put("refresh", key, record)
        for run in runs:
            store.put("run", run["id"], run)
        state.update(
            last_checked_at=now.isoformat(),
            pending_runs=[r["id"] for r in runs if r["status"] != "completed"],
            pending_pr_checks=pending_prs,
            audit_issues=issues,
            unchecked_prs=unchecked,
        )
        records = store.values("refresh")
        if not state.get("clean_since") and not state.get("needs_repair") and not failures and not issues:
            after = [r for r in records if timestamp(r["created_at"]) >= coverage_at and r["scheduled"]]
            offline = any(
                r["name"] == "Test Feed Generation"
                and r["head_branch"] == "main"
                and r["conclusion"] == "success"
                and r["head_sha"] == state["last_repair_sha"]
                for r in runs
            )
            if {r["type"] for r in after} == {"requests", "selenium"} and offline:
                state["clean_since"] = max(
                    min(r["completed_at"] for r in after if r["type"] == kind) for kind in ("requests", "selenium")
                )
        state["earliest_completion_at"] = (
            (timestamp(state["clean_since"]) + timedelta(hours=state.get("required_clean_hours", 10))).isoformat()
            if state.get("clean_since")
            else None
        )
        state["monitoring_status"] = (
            "repair needed"
            if state.get("needs_repair")
            else ("observing clean window" if state.get("clean_since") else "awaiting post-repair checks")
        )
        report = {
            "checked_at": now.isoformat(),
            "runs": len(runs),
            "new_errors": new_failures,
            "needs_repair": state.get("needs_repair", False),
            "issues": issues,
            "pending_runs": state["pending_runs"],
            "pending_pr_checks": pending_prs,
            "unchecked_prs": unchecked,
            "verified_attempts": [key for key, _ in evidence],
            "excluded_feeds": [name for name, cfg in registry.items() if not cfg.enabled],
            **window_status(state, records, now),
        }
        if failures:
            report["eligible"] = False
        store.put("state", "ci", state)
        store.put("state", "prs", prs)
        store.record("ci", report, now.isoformat())
    return report
