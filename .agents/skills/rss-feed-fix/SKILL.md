---
name: rss-feed-fix
description: Fix a broken RSS feed generator by downloading the live HTML, comparing it against the current CSS selectors in the generator, and updating any selectors that no longer match. Use when a feed is EMPTY or has stopped updating, after a validate_feeds.py failure, or when asked to "fix feed", "feed is broken", or "selectors broke".
disable-model-invocation: false
context: fork
agent: general-purpose
---

# RSS Feed Fix

You are the **RSS Feed Fix Agent**. A feed generator is broken — its CSS selectors no longer match the live site. Your job is to download the current HTML, identify what changed, update the selectors, verify the fix, and add a safety guard if one is missing.

## Inputs

The user should provide:
- The feed name (e.g. `weaviate`, `cursor`) OR the generator filename (e.g. `weaviate_blog.py`)

If neither is provided, check `feed_generators/validate_feeds.py` output or `feeds/feed_*.xml` to identify which feed is EMPTY.

## Workflow

### Step 1: Identify the generator and blog URL

1. Map the feed name to its generator:
   - Feed name → `feed_generators/{name}_blog.py`
   - If ambiguous, check `feeds.yaml` for the `script:` field
2. Read the generator file in full.
3. Note: `BLOG_URL`, `FEED_NAME`, and every CSS selector used in `parse_*` functions.

### Step 2: Fetch the live HTML

Use `curl` to download the raw HTML (not the WebFetch tool — it converts to markdown and loses class names):

```bash
curl -s "{BLOG_URL}" -o /tmp/feed_fix_live.html
```

If the site blocks `curl` (empty body or 403), try with a browser-like User-Agent:

```bash
curl -s -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36" "{BLOG_URL}" -o /tmp/feed_fix_live.html
```

If the site is JavaScript-rendered (SPA), note that and advise the user to provide a saved HTML file. Do not attempt to spin up Selenium during a fix — that requires a separate debugging session.

### Step 3: Diagnose the broken selectors

For each selector used in the generator's `parse_*` functions, check whether it still matches:

```bash
python3 -c "
import sys
sys.path.insert(0, 'feed_generators')
from bs4 import BeautifulSoup

with open('/tmp/feed_fix_live.html') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

# Test each selector from the generator
selectors = [
    'article.margin-bottom--xl',   # replace with actual selectors
    'a[itemprop=\"url\"]',
    'meta[itemprop=\"description\"]',
    'time[datetime]',
]
for sel in selectors:
    results = soup.select(sel)
    print(f'{len(results):4d} matches  {sel}')
"
```

Selectors that return 0 matches are broken. For each broken selector, find the replacement:

```bash
python3 -c "
import sys, re
with open('/tmp/feed_fix_live.html') as f:
    html = f.read()

from collections import Counter
from bs4 import BeautifulSoup
soup = BeautifulSoup(html, 'html.parser')

# Show top repeated tag+class combos — likely structural elements
combos = Counter()
for tag in soup.find_all(True):
    if tag.get('class'):
        combos[(tag.name, ' '.join(tag['class']))] += 1
print('TOP REPEATED ELEMENTS:')
for (tag, cls), count in sorted(combos.items(), key=lambda x: -x[1])[:30]:
    print(f'{count:4d}  <{tag} class=\"{cls}\">')
"
```

Then inspect a single representative element to confirm the new structure:

```bash
python3 -c "
from bs4 import BeautifulSoup
with open('/tmp/feed_fix_live.html') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')
# Replace with the new candidate wrapper selector
el = soup.select_one('article')  # or whatever looks right
if el:
    print(str(el)[:3000])
"
```

### Step 4: Update the generator

For each broken selector, make the minimal targeted edit using Edit tool. Preserve all logic — only change the selector strings and the attribute/text access that follows them.

Common selector patterns to look for in replacements:

| What to find | Typical old pattern | Look for new pattern |
|---|---|---|
| Article URL | `a[itemprop="url"]` | `a.{css-class-on-link}`, `header a`, `h2 a` |
| Description | `meta[itemprop="description"]` | `p.{description-class}`, `.summary`, `.excerpt` |
| Date | `time[datetime]` | usually still `time[datetime]` — rarely changes |
| Title | `h2`, `h3` | usually stable — check if now inside a different wrapper |
| Article wrapper | `article.{class}` | check for new class on `article` or `div` wrapper |

### Step 5: Add the empty-posts guard (if missing)

Check whether `main()` has a guard that prevents saving an empty feed:

```python
if not posts:
    logger.warning("No posts fetched — skipping feed update to avoid overwriting with empty feed")
    return False
```

This guard must appear **after** the posts list is built (after merge with cache for incremental generators) and **before** `save_cache()` and `save_rss_feed()`. If missing, add it.

### Step 6: Verify the fix

Test the updated parser directly against the downloaded HTML:

```bash
python3 -c "
import sys
sys.path.insert(0, 'feed_generators')
from {module_name} import parse_posts  # or parse_articles, parse_blog_html, etc.

with open('/tmp/feed_fix_live.html') as f:
    html = f.read()

posts = parse_posts(html)
# Some generators return (posts, has_next) — adjust accordingly
if isinstance(posts, tuple):
    posts, has_next = posts
    print(f'has_next={has_next}')

print(f'Found {len(posts)} posts')
for p in posts[:3]:
    print(f'  {p[\"title\"][:60]}')
    print(f'  {p[\"link\"]}')
    print(f'  {p.get(\"date\")}')
    print()
"
```

A successful fix shows 5+ posts. If still 0, revisit Step 3 — check the HTML more carefully; the site may require JavaScript rendering.

Then run the full generator to write the feed file:

```bash
uv run feed_generators/{name}_blog.py
```

Then validate:

```bash
uv run feed_generators/validate_feeds.py
```

The target feed should no longer appear as EMPTY.

### Step 7: Report

Summarize what changed:

| Selector | Old (broken) | New (fixed) |
|---|---|---|
| Article URL | `a[itemprop="url"]` | `a.blogCardTitle_wog0` |
| Description | `meta[itemprop="description"]` | `p.blogCardDescription_Y1fO` |

Note any guard that was added, and confirm the feed now passes validation.

## Notes

- Never change the feed's `FEED_NAME`, `BLOG_URL`, or output filename — only fix selectors.
- If the site structure changed so drastically that no useful selectors remain, report back before rewriting — a full rewrite needs user sign-off.
- If the live HTML is a JavaScript SPA shell (near-empty body), note this explicitly — Selenium is required and this skill cannot fix it unattended.
- Clean up `/tmp/feed_fix_live.html` after verifying if desired.
