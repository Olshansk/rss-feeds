# RSS feeds maintenance schedule

This is a reference for the existing Codex heartbeat, not a second scheduler.

| Setting | Value |
| --- | --- |
| Name | `rss-feeds-maintainer` |
| Existing ID | `rss-ci-clean-window-monitor` |
| Cadence | Every three hours |
| Scope | This checkout of `Olshansk/rss-feeds` |
| Policy | [RSS feeds maintainer skill](../.agents/skills/rss-feeds-maintainer/SKILL.md) |
| Runtime state | Local SQLite audit database under `.cache/scheduled_tasks/` |

To manage this on an authorized maintainer's machine, open the local Codex
maintenance thread for this checkout. Update the existing heartbeat in place.
Only if transferring ownership or recovering a missing schedule, coordinate with
the old owner to ensure there is exactly one active heartbeat before registering
a new recurring heartbeat in the local checkout. Reuse the cadence above and
configure local GitHub access separately; never commit credentials.

Suggested prompt for that heartbeat:

> Audit this repository once per wake. Read and follow the repo-local RSS feeds
> maintainer skill at `.agents/skills/rss-feeds-maintainer/SKILL.md`. Use
> `make scheduled_heartbeat` if present in the maintenance checkout. On a
> checkout without that incremental helper, the documented `scheduled_ci`,
> `scheduled_prs`, and `scheduled_events` targets are the manual audit fallback,
> not extra scheduled jobs. When there is nothing actionable, stop. Keep
> unresolved evidence and previous decisions in the local audit database. Do
> not reinstate the old continuous clean-window goal or change publication jobs.

The GitHub Actions that publish ordinary and Selenium feeds still run hourly
at :00 and :30 respectively. This schedule only audits and coordinates repairs.
