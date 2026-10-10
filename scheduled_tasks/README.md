# Scheduled tasks <!-- omit in toc -->

Run the CI and PR audits from this repository. Reuse the existing Codex heartbeat and GitHub runners; no VM, daemon, or paid database is required.

## Table of contents <!-- omit in toc -->

- [Commands](#commands)
- [Evidence and state](#evidence-and-state)
- [CI operating instructions](#ci-operating-instructions)
- [PR operating instructions](#pr-operating-instructions)
- [Feed/source comparisons](#feedsource-comparisons)
- [Repair history and exclusions](#repair-history-and-exclusions)

## Commands

Run a fresh CI audit:

```sh
make scheduled_ci
```

Inspect open PRs and their current checks:

```sh
make scheduled_prs
```

Record new GitHub activity (with explicit history-gap detection):

```sh
make scheduled_events
```

Read the checkpoint:

```sh
make scheduled_status
```

Import the previous monitor once:

```sh
uv run python -m scheduled_tasks import-history .cache/ci-reliability/state.json
```

After deploying a reviewed repair, reset the window with its full commit SHA and a concrete reason:

```sh
uv run python -m scheduled_tasks repair --sha COMMIT_SHA --reason 'Describe the verified repair'
```

The CLI requires authenticated `gh` access to the repository.
`--database` and `--repository` precede the subcommand.
Run from the repository root.

## Evidence and state

- SQLite: `.cache/scheduled_tasks/tasks.sqlite3`, ignored by Git.
- `records`: current checkpoint, run metadata, exact attempts, raw logs, refresh coverage, PR checks, and failures.
- `observations`: append-only audit, repair, import, and exception records.
- Database writes are transactional. An interrupted audit does not advance the checkpoint.
- Code, tests, these instructions, and repair context belong in Git. Runtime logs and the database remain local; back up the database with SQLite's backup API if needed.
- Import preserves the legacy history and available logs, then fresh audits independently verify post-repair evidence. The original files remain intact.
- A green run is evidence of execution, not proof that its source content is correct.

## CI operating instructions

The heartbeat must read this document and run `make scheduled_ci` at least once every 30 minutes while the clean-window goal is active.
Do not start a second polling process.

1. Check the native goal and audit result. Paginate all repository runs, including PR workflows, and inspect changed attempts and pending work.
2. Investigate every new failure from its stored exact-attempt logs. Treat tool/API errors as incomplete coverage, never success.
3. Apply the simplest economical repair. Preserve unrelated work. The user authorized committing and pushing CI fixes and pausing problematic feeds, with explicit disclosure.
4. Run meaningful offline checks and relevant live validation. Record each deployed repair with the CLI; any repair or newly observed CI failure invalidates the clean window.
5. Start the candidate window only after post-repair offline checks and complete scheduled HTTP/Selenium refreshes pass. Keep checking every 30 minutes.
6. Require ten consecutive error-free hours, successful scheduled refreshes in every elapsed hourly slot, exact coverage of enabled feeds, active workflows, and no pending runs/checks at the final audit.
7. Review the source freshness and published XML evidence before final completion. The CLI's `eligible` result is a candidate for this review, not automatic goal completion.
8. Only after that review, mark the native goal complete and pause the existing `rss-ci-clean-window-monitor` heartbeat.

Do not disguise cached output, skipped feeds, missing schedules, or swallowed exceptions as successful refreshes.
Do not bypass the existing browser security restriction.
Do not spend money on extra infrastructure without evidence it is needed.

## PR operating instructions

`make scheduled_prs` lists all open PRs with pagination and current head SHAs, reviews, and checks.
It stores each inventory in the same database.
`make scheduled_events` stores new event IDs and payloads there too. GitHub limits this activity feed to 300 events / 90 days; missing the previous boundary is reported as a coverage gap. CI and PR inventories remain separate complete paginated audits.
It does **not** merge PRs automatically: the dictated request did not establish the automatic merge scope, and clarification is pending.

Before any authorized merge, inspect the full diff and discussion, resolve conflicts without overwriting unrelated work, run relevant checks, require nonempty green current-head checks and a review of that exact head, and recheck the SHA immediately before merging.
A PR with no checks is unchecked, not green.
Use a merge command with an expected-head SHA guard; do not enable blind auto-merge or bypass branch protections.
Any merged feed/CI repair resets the clean-window timer and requires post-merge validation.

## Feed/source comparisons

The dictated “content and block” / “OCI documents” phrases are awaiting clarification.
The provisional interpretation is source-blog content versus generated RSS, and CI errors.
Do not silently treat an OCI-document request as implemented.

For a feed/source review, compare independently captured current source entries with the published XML: canonical article URL, title, publication date, and appropriate description/content.
Preserve historical items; incremental feeds need not equal the entire current listing.
Distinguish intentional future-publication deferrals from omitted published entries.
Use `compare-content` with a JSON snapshot containing `source_url`, ISO `captured_at`, `method`, and `items` (each with `link`, `title`, and optional ISO `published_at`). The sample must be no more than 30 minutes old.

```sh
uv run python -m scheduled_tasks compare-content --snapshot /tmp/source-sample.json --xml feeds/feed_ollama.xml
```

The helper stores the exact snapshot, XML, and result in the database. It checks sampled URLs, titles, and supplied dates; body/description parity still requires source-specific review. It does not capture websites or repair mismatches automatically.

Record source URL, capture time, extraction method, and discrepancies in the task database.
Fix demonstrated mismatches and test the specific regression.
Do not infer content equivalence from matching feed counts or from rerunning the same scraper.

## Repair history and exclusions

- `63f971194`: Claude public-resource API migration; historical entries preserved.
- `9e568668bf292395bb7dff177080346ca63f1318`: preserve original arXiv dates during Eleuther metadata enrichment; require a fresh listing.
- `347a7c899d847534a69459b4df73bdc9a979a1ae`: user-authorized Perplexity pause.
- `1752a39176d58547972bfc8a9dbb69dd05914d99`: defer future-dated source entries at publication, retaining original dates/cache and logging deferrals. Fixed the AI FIRST Podcast failures caused by an October 16 episode appearing early.
- Post-repair validation: [offline checks 38067810541](https://github.com/Olshansk/rss-feeds/actions/runs/38067810541), [28 HTTP feeds 38067820232](https://github.com/Olshansk/rss-feeds/actions/runs/38067820232), [five Selenium feeds 38068597899](https://github.com/Olshansk/rss-feeds/actions/runs/38068597899).
- Perplexity Hub and The Batch remain intentionally paused. Preserve their generator code and published XML; exclude them from successful-refresh claims.
- The earlier October 8 clean window was completed. New October 9 failures invalidated any continuing all-clear claim and led to the October 10 repair. A past clean window never guarantees future reliability.
