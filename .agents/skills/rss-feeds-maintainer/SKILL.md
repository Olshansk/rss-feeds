---
name: rss-feeds-maintainer
description: Triage scheduled RSS refresh failures in Olshansk/rss-feeds, rerun first, and test and merge narrowly scoped repair PRs when a repository defect persists.
---

# RSS feeds maintenance

Use the existing three-hour maintenance heartbeat and its [schedule reference](../../../scheduled_tasks/maintenance-schedule.md). Do not change hourly publishing schedules. Use the [runbook](../../../scheduled_tasks/README.md) for evidence and state.

1. **Identify an actionable failure.** Record the workflow, run ID, attempt and failing step. Ignore already tracked retries and stale failures whose recovery is proven by a newer equivalent run (check the same affected source/job, not just the banner). Missing logs, permissions failures, cancelled runs and old queue stalls are not code defects.
2. **Rerun once before repair.** For a new unresolved, eligible failure, use the narrowest applicable GitHub rerun (failed jobs when sufficient; the whole run when needed). Reuse a retry already started by someone else. Persist the attempt in the audit record and wait for its terminal result, checking on the next wake if needed. If the rerun succeeds, close the incident with evidence; do not change code. If GitHub won't rerun it or a retry would be unsafe, record the blocker; don't skip straight to a repair.
3. **Fix only a verified repo defect.** If the retry also fails and the exact logs show a fixable defect, isolate a topic branch and open a targeted PR. This can include a scraper update for a source redesign or a change to this repo's own site/layout needed to restore the feed. Do not work around upstream access controls, change feed scope, or make code changes just because a site is temporarily down. Test the regression offline and validate against the live source when applicable; confirm generated XML and historical IDs are preserved.
4. **Merge only that repair PR.** Review the complete diff and checks on the exact current head. Require a nonempty successful CI result and every required check and review; revalidate after a head change. Merge with an expected-head SHA guard, without bypassing branch protection. No direct-push repairs, unrelated PR merges, or blanket auto-merge. The automated publishing workflows that commit generated output are unchanged.
5. **Verify the next relevant scheduled refresh.** Check the affected source/job, not just the green summary, and confirm the published output. Record the merged commit and run/attempt evidence in the audit database. If verification fails or remains unavailable, keep the incident open and report the blocker under the existing notification policy.
