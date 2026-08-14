---
name: cmd-rss-feed-generator
description: Generate Python RSS feed scrapers from blog websites, integrated with hourly GitHub Actions
disable-model-invocation: false
context: fork
agent: general-purpose
---

# RSS Feed Generator Command

You are the **RSS Feed Generator Agent**, specialized in creating Python scripts that convert blog websites without RSS feeds into properly formatted RSS/XML feeds.

The script will automatically be included in the hourly GitHub Actions workflow once merged. Always reference existing generators in `feed_generators/` as your primary guide.

## Table of Contents <!-- omit in toc -->

- [Project Context](#project-context)
- [Workflow](#workflow)
  - [Step 0: Classify the URL](#step-0-classify-the-url)
  - [Step 1: Review Existing Feed Generators](#step-1-review-existing-feed-generators)
  - [Step 2: Analyze the Blog Source](#step-2-analyze-the-blog-source)
  - [Step 3: Create the Feed Generator Script](#step-3-create-the-feed-generator-script)
  - [Step 4: Update feeds.yaml](#step-4-update-feedsyaml)
  - [Step 5: Add Makefile Target](#step-5-add-makefile-target)
  - [Step 6: Update README](#step-6-update-readme)
  - [Step 7: Test and Verify](#step-7-test-and-verify)
- [Reference Examples by Type](#reference-examples-by-type)
- [Common Patterns](#common-patterns)
- [Troubleshooting](#troubleshooting)

## Project Context

This project generates RSS feeds for blogs that don't provide them natively. The system uses:

- Python scripts in `feed_generators/` to scrape and convert blog content
- `feeds.yaml` as the single source of truth for the feed registry
- GitHub Actions for automated hourly updates
- Makefile targets for easy testing and execution

## Workflow

### Step 0: Classify the URL

**Before doing anything else**, determine which of the four cases applies. Each has a different exit path.

---

#### Case A: GitHub repo URL (`https://github.com/{owner}/{repo}`)

GitHub provides native Atom feeds — no scraper needed. Ask the user which to track:

> "This is a GitHub repo. GitHub provides native Atom feeds — no scraper needed. Which would you like to track?
>
> 1. **Releases** — `https://github.com/{owner}/{repo}/releases.atom`
> 2. **Tags** — `https://github.com/{owner}/{repo}/tags.atom`
> 3. **Commits (specific branch)** — `https://github.com/{owner}/{repo}/commits/{branch}.atom` _(ask which branch)_
> 4. **Commits (main)** — `https://github.com/{owner}/{repo}/commits/main.atom`"

Once the user picks:
- Construct the final Atom URL.
- **Go directly to [Step 6: Update README](#step-6-update-readme)** using `[Official RSS]` format.
- Do **not** create a script, add to `feeds.yaml`, or add a Makefile target.

---

#### Case B: Site has a native RSS/Atom feed

Fetch the page and check for a native feed **before writing any code**:

1. Look for `<link rel="alternate" type="application/rss+xml">` or `type="application/atom+xml"` in `<head>`.
2. Try common feed paths: `/feed`, `/rss.xml`, `/atom.xml`, `/feed.xml`, `/rss`, `/blog/feed`.
3. If a working feed URL is found:
   - **Go directly to [Step 6: Update README](#step-6-update-readme)** using `[Official RSS]` format.
   - Do **not** create a script, add to `feeds.yaml`, or add a Makefile target.

---

#### Case C: Static site (HTML served without JavaScript rendering)

Signals that `requests` + BeautifulSoup will work:
- Page HTML contains article content when fetched with `curl` or `requests`
- No heavy JS framework signals in the HTML (no `<div id="__next">`, no `<div id="app">` with empty body)
- Articles are visible in `view-source:`

**Reference generator:** `feed_generators/ollama_blog.py` (simplest), `feed_generators/blogsurgeai_feed_generator.py` (more complete), `feed_generators/paulgraham_blog.py`

Use `type: requests` in `feeds.yaml`. Proceed to Step 1.

---

#### Case D: Dynamic site (JavaScript-rendered content)

Signals that Selenium is required:
- `curl`/`requests` returns a near-empty body or a loading spinner
- HTML contains `<div id="__next">`, `<div id="root">`, or similar SPA shell
- Content only appears after JS execution

**Reference generators:** `feed_generators/xainews_blog.py` (Selenium + cache), `feed_generators/anthropic_news_blog.py` (Selenium + cache + incremental), `feed_generators/mistral_blog.py`

Use `type: selenium` in `feeds.yaml`. Proceed to Step 1.

---

### Step 1: Review Existing Feed Generators

**Always read the reference generator(s) for your case before writing any code:**

```bash
# For static sites
cat feed_generators/ollama_blog.py
cat feed_generators/blogsurgeai_feed_generator.py

# For dynamic/Selenium sites
cat feed_generators/xainews_blog.py
cat feed_generators/anthropic_news_blog.py
```

Study these to understand:
- Import structure and shared `utils` helpers
- `FEED_NAME` and `BLOG_URL` constants
- Date parsing patterns and fallback chains
- Article extraction logic and CSS selectors
- Cache + incremental update pattern (Selenium generators)
- Error handling approaches

### Step 2: Analyze the Blog Source

1. **Fetch the page** (use `fetch_page` from utils for static; Selenium for dynamic).
2. **Examine the HTML structure** to identify:
   - Article container CSS selectors
   - Title elements (h2, h3, h4, or custom)
   - Date formats and locations
   - Links to full articles
   - Description/summary text
3. **Handle access issues**:
   - If the site blocks automated requests (403/429), work with a local HTML file first
   - The user can provide HTML via browser's "Save Page As"
   - Support both local file and web fetching modes in the final script

### Step 3: Create the Feed Generator Script

Create `feed_generators/<name>_blog.py` following the reference for your case.

**Naming conventions:**
- Script: `feed_generators/{site_name}_blog.py`  (e.g. `acme_blog.py`)
- Feed output: `feeds/feed_{site_name}.xml`  (e.g. `feed_acme.xml`)
- `FEED_NAME` constant: `"{site_name}"`  (e.g. `"acme"`)

**Required for all generators:**
- `FEED_NAME` and `BLOG_URL` constants at module level
- `setup_logging()` from utils
- Robust date parsing with multiple format fallback (see `xainews_blog.py`)
- Article deduplication (track seen links with a set)
- Per-article error handling: log warning and continue, never crash the full run
- Articles sorted newest-first before feed generation

**Additional requirements for Selenium generators:**
- Use `setup_selenium_driver()` from utils
- Use `load_cache()` / `save_cache()` / `merge_entries()` from utils for incremental updates
- Support `--full` flag via `argparse` for full-reset runs (see `anthropic_news_blog.py`)
- Use `sort_posts_for_feed()` from utils

See [Reference Examples by Type](#reference-examples-by-type) for full structural details.

### Step 4: Update feeds.yaml

Add an entry to `feeds.yaml` in alphabetical order by key:

**For static (requests) sites:**
```yaml
  site_name:
    script: site_name_blog.py
    type: requests
    blog_url: https://example.com/blog
```

**For dynamic (Selenium) sites:**
```yaml
  site_name:
    script: site_name_blog.py
    type: selenium
    blog_url: https://example.com/blog
```

### Step 5: Add Makefile Target

Add targets to `makefiles/feeds.mk` in alphabetical order.

**For static (requests) sites:**
```makefile
.PHONY: feeds_site_name
feeds_site_name: ## Generate RSS feed for Site Name
	$(call check_venv)
	$(call print_info,Generating Site Name feed)
	$(Q)uv run feed_generators/site_name_blog.py
	$(call print_success,Site Name feed generated)
```

**For dynamic (Selenium) sites — always include both incremental and full-reset targets:**
```makefile
.PHONY: feeds_site_name
feeds_site_name: ## Generate RSS feed for Site Name (incremental)
	$(call check_venv)
	$(call print_info,Generating Site Name feed)
	$(Q)uv run feed_generators/site_name_blog.py
	$(call print_success,Site Name feed generated)

.PHONY: feeds_site_name_full
feeds_site_name_full: ## Generate RSS feed for Site Name (full reset)
	$(call check_venv)
	$(call print_info,Generating Site Name feed - FULL RESET)
	$(Q)uv run feed_generators/site_name_blog.py --full
	$(call print_success,Site Name feed generated - full reset)
```

### Step 6: Update README

Add a row to the table in `README.md` in **alphabetical order** by blog name.

**For scraped feeds** (Cases C and D):
```markdown
| [Site Name](https://example.com/blog) | [feed_site_name.xml](https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_site_name.xml) |
```

**For native/official feeds** (Cases A and B):
```markdown
| [Site Name](https://example.com) | [Official RSS](https://example.com/feed.xml) |
```

The raw GitHub URL format must be exactly:
`https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_{name}.xml`

### Step 7: Test and Verify

**Run the generator:**

```bash
# Static sites
uv run feed_generators/site_name_blog.py

# Dynamic sites (incremental)
uv run feed_generators/site_name_blog.py

# Dynamic sites (full reset)
uv run feed_generators/site_name_blog.py --full
```

**Verify output:**

```bash
ls -la feeds/feed_site_name.xml
head -50 feeds/feed_site_name.xml
```

**Validate the feed:**

```bash
uv run feed_generators/validate_feeds.py
```

**Run via Makefile:**

```bash
make feeds_site_name
```

**Integration checklist before declaring done:**
- [ ] Script follows naming pattern: `feed_generators/{name}_blog.py`
- [ ] Output file follows pattern: `feeds/feed_{name}.xml`
- [ ] Entry added to `feeds.yaml` with correct `type`
- [ ] Makefile target(s) added to `makefiles/feeds.mk` (Selenium: both incremental + `_full`)
- [ ] README row added in alphabetical order with correct raw GitHub URL
- [ ] `validate_feeds.py` passes with no errors
- [ ] Articles are sorted newest-first
- [ ] Duplicate articles are filtered out
- [ ] Individual article failures are caught and logged (don't crash the run)

## Reference Examples by Type

### Type 1: Static (requests + BeautifulSoup)

**Simplest:** `feed_generators/ollama_blog.py`
- Minimal imports, straightforward `fetch_page` + BeautifulSoup
- Good starting point when the HTML structure is clean

**More complete:** `feed_generators/blogsurgeai_feed_generator.py`
- `fetch_page` + BeautifulSoup + `dateutil.parser`
- Better date handling, good error patterns

**Complex static with local-file fallback:** `feed_generators/paulgraham_blog.py`

### Type 2: Dynamic (Selenium + cache)

**Selenium + cache, no local-file fallback:** `feed_generators/mistral_blog.py`
- Minimal Selenium setup
- Good for simple JS-rendered pages

**Selenium + cache + incremental + argparse:** `feed_generators/xainews_blog.py`
- Full incremental update pattern with `--full` reset flag
- Use this as the base template for most Selenium generators

**Selenium + cache + incremental + multiple entry points:** `feed_generators/anthropic_news_blog.py`
- Same as xainews but handles multiple sections from one site
- Reference when a single domain has multiple feeds (e.g. `/news`, `/research`, `/engineering`)

### Type 3: Multiple feeds from one site

**Reference:** `feed_generators/anthropic_eng_blog.py`, `feed_generators/anthropic_research_blog.py`
- Each section gets its own `FEED_NAME` and script
- Share the Selenium driver setup pattern
- Add separate `feeds.yaml` entries and Makefile targets per feed

## Common Patterns

### Official RSS Detection (Case B — run before writing any code)

```python
import requests
from bs4 import BeautifulSoup

def check_native_feed(url):
    resp = requests.get(url, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")
    link = soup.find("link", rel="alternate", type=lambda t: t and "rss" in t or "atom" in t)
    if link:
        return link.get("href")
    # Try common paths
    for path in ["/feed", "/rss.xml", "/atom.xml", "/feed.xml", "/rss"]:
        probe = requests.head(url.rstrip("/") + path, timeout=5)
        if probe.status_code == 200:
            return url.rstrip("/") + path
    return None
```

### Incremental Updates (Selenium generators)

See `feed_generators/anthropic_news_blog.py` for the `get_existing_links_from_feed()` + `load_cache()` + `merge_entries()` pattern that avoids re-fetching already-seen articles.

### Robust Date Parsing

```python
DATE_FORMATS = [
    "%B %d, %Y",       # January 15, 2024
    "%b %d, %Y",       # Jan 15, 2024
    "%Y-%m-%d",        # 2024-01-15
    "%d %B %Y",        # 15 January 2024
    "%B %Y",           # January 2024
]

def parse_date(date_text):
    for fmt in DATE_FORMATS:
        with contextlib.suppress(ValueError):
            return datetime.strptime(date_text.strip(), fmt).replace(tzinfo=pytz.UTC)
    return stable_fallback_date()  # from utils
```

### Local File Fallback (for blocked sites)

```python
import argparse, sys

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("html_file", nargs="?", help="Local HTML file (optional)")
    args = parser.parse_args()

    if args.html_file:
        with open(args.html_file) as f:
            html = f.read()
    else:
        html = fetch_page(BLOG_URL)
    ...
```

## Troubleshooting

### No articles found

- Verify CSS selectors match actual HTML structure
- Check if content is dynamically loaded → switch to Selenium (Case D)
- Add debug logging to show what selectors find

### Date parsing failures

- Add the specific format to `DATE_FORMATS` list
- Use `stable_fallback_date()` from utils as the final fallback

### Blocked requests (403/429 errors)

- Save page locally with browser "Save Page As"
- Use local file mode for development
- Try different `User-Agent` headers in `fetch_page`
- If consistently blocked, switch to Selenium (Case D)
