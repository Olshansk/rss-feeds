# AGENTS.md <!-- omit in toc -->

Instructions for Claude Code and contributors working on this repository.

## Table of Contents <!-- omit in toc -->

- [Project Overview](#project-overview)
- [Commands](#commands)
- [Architecture](#architecture)
  - [Feed Generator Patterns](#feed-generator-patterns)
  - [When to Use Each Pattern](#when-to-use-each-pattern)
  - [Feed Link Setup (Important)](#feed-link-setup-important)
- [Adding a New Feed](#adding-a-new-feed)
  - [Step 1: Analyze the Target Blog](#step-1-analyze-the-target-blog)
  - [Step 2: Download HTML Sample](#step-2-download-html-sample)
  - [Step 3: Generate the Feed Script](#step-3-generate-the-feed-script)
  - [Step 4: Test Locally](#step-4-test-locally)
  - [Step 5: Register the Feed](#step-5-register-the-feed)
  - [Step 6: PR Checklist](#step-6-pr-checklist)
- [Troubleshooting](#troubleshooting)
- [GitHub Actions](#github-actions)

## Project Overview

RSS Feed Generator creates RSS feeds for blogs that don't provide them natively. Feed generators scrape blog pages and output `feed_*.xml` files to the `feeds/` directory. A GitHub Action runs hourly to regenerate and commit updated feeds.

## Commands

```bash
# Environment setup
make env_install          # Create venv and install dependencies (uses uv)
source .venv/bin/activate # Activate virtual environment

# Generate feeds
make feeds_generate_all   # Run all feed generators
make feeds_<name>         # Run specific feed (e.g., feeds_ollama, feeds_anthropic_news)

# Development
make dev_format           # Format code with black and isort
make dev_test_feed        # Run test feed generator

# Run single generator directly
python feed_generators/ollama_blog.py

# CI/CD
make ci_trigger_feeds_workflow    # Trigger GitHub Action manually
make ci_run_feeds_workflow_local  # Test workflow locally with act
```

## Architecture

```
feed_generators/           # Python scripts that scrape blogs and generate RSS
  run_all_feeds.py         # Orchestrator that runs all generators
  utils.py                 # Shared utilities (setup_feed_links, get_project_root, etc.)
  <source>_blog.py         # Individual feed generators
feeds/                     # Output directory for feed_*.xml files
cache/                     # JSON cache for paginated/dynamic feeds
makefiles/                 # Modular Makefile includes (feeds.mk, env.mk, dev.mk, ci.mk)
```

### Feed Generator Patterns

Three patterns exist based on how the target site loads content:

#### 1. Simple Static (Default) <!-- omit in toc -->

For blogs where all content loads on first request.

**Examples**: `ollama_blog.py`, `paulgraham_blog.py`, `hamel_blog.py`

**Key functions**:
- `fetch_blog_content(url)` - HTTP request with User-Agent header
- `parse_blog_html(html)` - BeautifulSoup parsing for posts
- `generate_rss_feed(posts)` - Create feed using `feedgen`
- `save_rss_feed(fg, name)` - Write to `feeds/feed_{name}.xml`

**Cache**: Not needed (all posts fetched each run)

#### 2. Pagination + Caching <!-- omit in toc -->

For blogs with "Load More" or pagination that uses URL query params (`?page=2`).

**Examples**: `cursor_blog.py`, `dagster_blog.py`

**Key functions**:
- `load_cache()` / `save_cache(posts)` - JSON persistence in `cache/<source>_posts.json`
- `merge_posts(new, cached)` - Dedupe by URL, merge, sort by date
- `fetch_all_pages()` - Follow pagination until no next link

**Cache behavior**:
- **First run / `--full` flag**: Fetch all pages, populate cache
- **Incremental (default)**: Fetch page 1 only, merge with cache
- **Dedupe**: By URL, sorted by date descending

#### 3. Selenium + Click "Load More" <!-- omit in toc -->

For JS-heavy sites where content loads dynamically via JavaScript button clicks.

**Examples**: `anthropic_news_blog.py`, `anthropic_research_blog.py`, `openai_research_blog.py`

**Key functions**:
- `setup_selenium_driver()` - Headless Chrome with `undetected-chromedriver`
- `fetch_news_content()` - Load page, click buttons, return final HTML

**Selenium specifics**:
- Uses `undetected-chromedriver` to avoid bot detection
- Clicks "See more"/"Load more" button repeatedly
- Waits for content to load between clicks
- `max_clicks` safety limit (default: 20) to prevent infinite loops

**Cache**: Should use caching (like Pattern 2) for efficiency, but currently refetches all posts each run.

### When to Use Each Pattern

| Site Behavior | Pattern | Example | Cache? |
|--------------|---------|---------|--------|
| All posts on single page | Simple Static | `ollama_blog.py` | No |
| URL-based pagination (`?page=2`) | Pagination + Caching | `dagster_blog.py` | Yes |
| JS button loads more content | Selenium + Click | `anthropic_news_blog.py` | Recommended |

**Key libraries**: `requests`, `beautifulsoup4`, `feedgen`, `selenium`, `undetected-chromedriver`

### Feed Link Setup (Important)

The main `<link>` element must point to the original blog, not the feed URL. Use the helper:

```python
from utils import setup_feed_links

fg = FeedGenerator()
# ... set title, description, etc.
setup_feed_links(fg, blog_url="https://example.com/blog", feed_name="example")
```

**Why this matters**: In `feedgen`, link order determines which URL becomes the main `<link>`:
- `rel="self"` must be set **first** → becomes `<atom:link rel="self">`
- `rel="alternate"` must be set **last** → becomes the main `<link>`

Wrong order produces `<link>https://.../feed_example.xml</link>` instead of the blog URL.

## Adding a New Feed

### Step 1: Analyze the Target Blog

Before writing code, determine which pattern to use:

1. **Open the blog** in your browser
2. **Check for pagination**:
   - URL changes to `?page=2` or `/page/2` → **Pattern 2 (Pagination)**
   - No URL change but "Load More" button exists → **Pattern 3 (Selenium)**
   - All posts visible on single page → **Pattern 1 (Simple Static)**
3. **Check for JavaScript loading**:
   - Open DevTools → Network tab → Reload
   - If posts appear after JS execution (XHR requests) → **Pattern 3 (Selenium)**
   - If posts are in initial HTML → **Pattern 1 or 2**

### Step 2: Download HTML Sample

```bash
# For static sites (Pattern 1 or 2)
curl -o sample.html "https://example.com/blog"

# For JS-heavy sites (Pattern 3)
# Use browser: View Page Source won't work
# Instead: DevTools → Elements → Copy outer HTML after page loads
```

### Step 3: Generate the Feed Script

Use Claude Code with the generator prompt:

```bash
Use @cmd_rss_feed_generator.md to convert @sample.html to a RSS feed for https://example.com/blog
```

Claude will:
- Analyze the HTML structure
- Choose the appropriate pattern
- Generate `feed_generators/<source>_blog.py`

### Step 4: Test Locally

```bash
# Install dependencies
make env_install
source .venv/bin/activate

# Run the generator
python feed_generators/<source>_blog.py

# Verify output
cat feeds/feed_<source>.xml | head -50

# For paginated feeds, test full fetch
python feed_generators/<source>_blog.py --full
```

**Verify**:
- [ ] Feed XML is valid (no parsing errors)
- [ ] `<link>` points to blog URL, not feed URL
- [ ] Posts have titles, dates, and links
- [ ] Dates are in correct order (newest first)

### Step 5: Register the Feed

1. **Add Make target** in `makefiles/feeds.mk`:
   ```makefile
   .PHONY: feeds_<source>
   feeds_<source>: ## Generate RSS feed for <Source Name>
   	$(call check_venv)
   	$(call print_info,Generating <Source Name> feed)
   	$(Q)python feed_generators/<source>_blog.py
   	$(call print_success,<Source Name> feed generated)
   ```

2. **Update README.md table** (alphabetical order):
   ```markdown
   | [Source Name](https://example.com/blog) | [feed_<source>.xml](https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_<source>.xml) |
   ```

3. **Add to `run_all_feeds.py`** if not auto-discovered

### Step 6: PR Checklist

Before submitting your PR, verify:

- [ ] `make dev_format` passes (code formatting)
- [ ] `python feed_generators/<source>_blog.py` runs without errors
- [ ] `feeds/feed_<source>.xml` is generated and valid
- [ ] Make target added to `makefiles/feeds.mk`
- [ ] README.md table updated
- [ ] For paginated/dynamic feeds: cache file created in `cache/` on first run
- [ ] Feed `<link>` points to original blog (not the XML feed URL)

## Troubleshooting

**"No posts found" or empty feed**
- HTML structure may have changed; re-download sample and update selectors
- For Selenium: increase wait times or check if site blocks headless browsers

**Feed `<link>` shows XML URL instead of blog URL**
- Use `setup_feed_links()` helper from `utils.py`
- Ensure `rel="self"` is set before `rel="alternate"`

**Selenium bot detection**
- `undetected-chromedriver` should handle most cases
- Try increasing wait times between clicks
- Some sites may require additional headers or cookies

**Cache not updating**
- Delete `cache/<source>_posts.json` and run with `--full`
- Check `merge_posts()` deduplication logic

**Date parsing errors**
- Add the date format to the `date_formats` list
- Use `stable_fallback_date()` for entries without parseable dates

## GitHub Actions

- `run_feeds.yml` - Runs hourly, executes `run_all_feeds.py`, commits updated XML files
- `test_feed.yml` - Tests feed generation on PRs
