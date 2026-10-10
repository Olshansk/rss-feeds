# Feed reliability <!-- omit in toc -->

A successful process is insufficient: a feed must contain current source items, valid dates, unique identities, and newest-first output.

## Contents <!-- omit in toc -->

- [Shared patterns](#shared-patterns)
- [Repair workflow](#repair-workflow)
- [CI and resource use](#ci-and-resource-use)
- [Validation boundaries](#validation-boundaries)

## Shared patterns

| Module | Responsibility |
|---|---|
| `static_pages.py` | Bounded HTTP requests and pagination; reject empty pages and pagination loops. |
| `dynamic_pages.py` | Chrome setup, article waits, expansion controls, and guaranteed browser cleanup. `RSS_CHROMEDRIVER` can select a compatible locally installed driver. |
| `html_cards.py` | Semantic heading/link/date cards, including featured cards with dates in their parent container. |
| `dates.py` | Explicit date formats, including SEPT.; preserve source time zones and reject unknown dates. |
| `changelog.py` | Mintlify version anchors, rich release descriptions, and legacy release GUIDs. |
| `native_rss.py` | Strict native RSS parsing for existing generated endpoints. |
| `embedded_data.py` | Decode JSON records in Next.js Flight script chunks without executing JavaScript. |
| `paper_dates.py` | Original arXiv publication dates; explicitly label year-only dates for other research records. |
| `feed_history.py` | Recover checked-in history, reject empty live extractions, and preserve subscriber identities across migrations. Title matching requires explicit opt-in. |
| `utils.py` | Cache normalization, fresh-data merging, feed links, deduplication, newest-first sorting, and atomic validated publication. Legacy HTTP/browser imports remain compatible. |
| `validate_feeds.py` | Reject missing dates, invalid dates, future dates, duplicate links/GUIDs, empty feeds, and incorrect ordering. Report age separately. |

Keep site-specific selectors in their generator. Reuse a shared helper when the actual structure matches; do not accumulate unrelated site exceptions in the helper.

## Repair workflow

1. Download the current source and identify missing titles or dates against the published XML.
2. Add a small source fragment to `tests/fixtures/` and exercise its parser through `tests/source_cases.json` or a focused unittest.
3. Run offline regression tests.
4. Run the affected generator against its live source; confirm newest titles, dates, unique entries, and GUID continuity.
5. Verify the output before committing. A stale but accurately mirrored source is different from failed extraction.

Offline tests:

```bash
make dev_test_unit
```

One live feed, including output-refresh checks:

```bash
uv run feed_generators/run_all_feeds.py --feed groq
```

All persisted feeds:

```bash
uv run feed_generators/validate_feeds.py
```

Lint and formatting:

```bash
make dev_lint
```

## CI and resource use

- `test_feed.yml` runs offline fixtures, lint, registry validation, and XML validation in one job with locked dependencies.
  Relevant code, test, registry, Makefile, and workflow changes trigger it; feed XML changes also trigger it on PRs.
  Superseded CI runs are canceled, and bot XML pushes do not start code CI.
- The synthetic generator fixture runs through the real subprocess runner and shared writer with `uv` offline.
  It verifies valid generation, unchanged content, real article updates, and rejection of a process that exits without writing.
  Batch fixtures also simulate HTTP 403, 429, and 503 and verify that failures preserve the published feed.
- The hourly HTTP and browser workflows remain live refresh jobs, separate from deterministic code checks.
  Each reports per-feed outcomes in its GitHub job summary; a failed refresh remains a failure.
  Quiet source publication dates are informational after successful extraction, not code-test failures.
- Both refresh workflows validate locally before publication and after merging remote changes.
  `validate_feeds.yml` remains available manually; it no longer starts a redundant runner after every refresh.
- An unchanged feed retains its published bytes and build date, preventing timestamp-only commits.
  The writer still atomically replaces the local file, so the runner can distinguish a successful unchanged refresh from a generator that did nothing.
- HTTP failures log available `Retry-After`, Cloudflare challenge, and rate-limit diagnostics without automatic retry loops.
  A 403 alone does not establish whether the publisher applied a rate limit or a different access rule.

## Validation boundaries

- The runner rejects timeout, nonzero exit, unchanged/missing output, and invalid XML content. Cache merges must require nonempty fresh extraction before merging historical entries.
- Production workflows publish validated updates even if a different generator fails; the overall run remains failed so the broken source stays visible. Merge conflicts and post-merge validation failures stop publication.
- Feed writes validate first and replace the destination atomically. Invalid output leaves the last working XML untouched.
- Complete entries with future source timestamps are deferred by the shared writer until their publication time.
  Source dates and cached entries remain intact, and each deferral appears in CI logs and the per-feed summary.
  Missing/invalid dates still fail validation; an entirely future-dated feed is empty and cannot replace published XML.
- History uses exact links or GUIDs by default. Explicit title matching is reserved for source migrations and only matches unique historical titles.
- Publication age is a warning, since quiet blogs can be correct. Compare the newest source article to distinguish a quiet source from a frozen scraper.
- RSS requires a full timestamp. For research sources that provide only a year and lack arXiv metadata, January 1 represents that year and the description discloses this precision. Do not pretend it is an exact publication day.
- Prefer a publisher-provided RSS feed when available. The Batch's automatic refresh is paused with `enabled: false` in `feeds.yaml` because hosted-runner requests receive HTTP 403 challenges. Its existing XML and generator are retained for later review. Re-enable the registry entry after verifying publisher access from GitHub. Offline fixtures continue to validate parsing and failure handling.
- Offline fixture tests do not replace live checks. Current layouts can change independently of CI.
