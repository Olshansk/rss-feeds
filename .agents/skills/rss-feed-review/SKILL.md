---
name: cmd-rss-feed-review
description: Review RSS feed generators and their XML output for broken selectors, missing error handling, stale cache logic, feed link conventions, empty/malformed feeds, and duplicate entries. Use when asked to "review feed", "check feed quality", "audit feeds", or after creating/modifying a feed generator.
disable-model-invocation: true
---

# RSS Feed Review

Review RSS feed generators and their output XML for correctness, robustness, and adherence to project conventions.

## Instructions

1. **Determine scope** — review all feed generators by default, or a specific one if the user specifies.
2. **Read the target generator(s)** and their corresponding `feeds/feed_*.xml` output files.
3. **Read `feed_generators/utils.py`** to understand shared helpers.
4. **Evaluate against the checklists below.** For every finding, cite `file_path:line_number`.
5. **If everything looks good**, say so briefly.

## Generator Code Review

### Selectors & Parsing

- Are CSS selectors specific enough to survive minor site redesigns?
- Are selectors targeting semantic elements (article, h2) over generated class names?
- Is there fallback logic if a selector returns no results?

### Error Handling

- Does `fetch_*` use `timeout=` on requests?
- Are HTTP errors handled (`response.raise_for_status()` or status check)?
- Are Selenium waits using explicit waits (`WebDriverWait`) rather than `time.sleep()`?
- Is the Selenium driver properly closed in a `finally` block?

### Feed Link Setup

**Critical convention** (from AGENTS.md):

```python
from utils import setup_feed_links
setup_feed_links(fg, blog_url="https://...", feed_name="...")
```

- The main `<link>` must point to the original blog URL, NOT the feed URL
- `rel="self"` must be set **first**, `rel="alternate"` must be set **last**
- Generators should use the `setup_feed_links()` helper from `utils.py`
- Flag any generator that sets links manually instead of using the helper

### Cache Logic (Pagination & Selenium patterns only)

- Is cache loaded before fetching new articles?
- Are articles deduped by URL before saving?
- Is the cache sorted by date descending?
- Does the `--full` flag correctly bypass incremental logic?

### Pattern Compliance

- **Simple Static**: No cache needed, fetches all posts each run
- **Pagination + Caching**: URL-based pagination with JSON cache in `cache/`
- **Selenium + Click**: Uses `undetected-chromedriver`, clicks load-more buttons, caches results
- Is the generator using the right pattern for how the target site loads content?

## Feed XML Output Review

### Structure

- Does the feed have a `<title>`, `<link>`, and `<description>` in `<channel>`?
- Does every `<item>` have at least `<title>`, `<link>`, and `<pubDate>`?
- Is there an `<atom:link rel="self">` pointing to the feed URL?
- Does the main `<link>` point to the blog (not the feed file)?

### Content Quality

- Are there 0 items? (EMPTY — likely broken scraper)
- Is the newest item older than 60 days? (STALE — selectors may have broken)
- Are there duplicate `<link>` values across items?
- Are dates parseable as RFC 2822 (`pubDate` format)?
- Are titles non-empty and non-duplicated?

### Encoding

- Is the XML declaration present with `encoding="utf-8"`?
- Are special characters properly escaped in titles and descriptions?

## Output Format

For each finding:

```
[SEVERITY] file_path:line_number — description
```

Severities: `ERROR` (broken/will fail), `WARN` (fragile/convention violation), `INFO` (suggestion)

End with a summary table:

| Feed | Generator | XML Output | Issues |
|------|-----------|------------|--------|
| name | OK/WARN/ERROR | OK/WARN/ERROR | brief note |
