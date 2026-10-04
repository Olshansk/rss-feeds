# Feed reliability <!-- omit in toc -->

A successful process is insufficient: a feed must contain current source items, valid dates, unique identities, and newest-first output.

## Contents <!-- omit in toc -->

- [Shared patterns](#shared-patterns)
- [Repair workflow](#repair-workflow)
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

## Validation boundaries

- The runner rejects timeout, nonzero exit, unchanged/missing output, and invalid XML content. Cache merges must require nonempty fresh extraction before merging historical entries.
- Feed writes validate first and replace the destination atomically. Invalid output leaves the last working XML untouched.
- History uses exact links or GUIDs by default. Explicit title matching is reserved for source migrations and only matches unique historical titles.
- Publication age is a warning, since quiet blogs can be correct. Compare the newest source article to distinguish a quiet source from a frozen scraper.
- RSS requires a full timestamp. For research sources that provide only a year and lack arXiv metadata, January 1 represents that year and the description discloses this precision. Do not pretend it is an exact publication day.
- Prefer a publisher-provided RSS feed when available. The Batch uses its official `charonhub.deeplearning.ai/tag/the-batch/rss/` feed, maps links to the public website, and retains its older archive. Hosted-runner HTML requests to the main website are blocked.
- Offline fixture tests do not replace live checks. Current layouts can change independently of CI.
