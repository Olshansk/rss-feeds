# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
  <source>_blog.py         # Individual feed generators
feeds/                     # Output directory for feed_*.xml files
cache/                     # JSON cache for paginated feeds (cursor_posts.json, dagster_posts.json)
makefiles/                 # Modular Makefile includes (feeds.mk, env.mk, dev.mk, ci.mk)
```

### Feed Generator Patterns

Three patterns exist based on how the target site loads content:

#### 1. Simple Static (Default)

For blogs where all content loads on first request.

```
ollama_blog.py, paulgraham_blog.py, hamel_blog.py
```

- `fetch_blog_content(url)` - HTTP request with User-Agent header
- `parse_blog_html(html)` - BeautifulSoup parsing for posts
- `generate_rss_feed(posts)` - Create feed using `feedgen`
- `save_rss_feed(fg, name)` - Write to `feeds/feed_{name}.xml`

#### 2. Pagination + Caching

For blogs with "Load More" or pagination that uses URL query params.

```
cursor_blog.py, dagster_blog.py
```

- **Cache**: JSON file in `cache/<source>_posts.json` with `last_updated` and `posts`
- **Full fetch**: `python <source>_blog.py --full` to fetch all pages
- **Incremental**: Default mode fetches page 1 only, merges with cache
- **Dedupe**: By URL, sorted by date descending

Key functions:
- `load_cache()` / `save_cache(posts)` - JSON persistence
- `merge_posts(new, cached)` - Dedupe and merge
- `fetch_all_pages()` - Follow pagination until no next link

#### 3. Selenium + Click "Load More"

For JS-heavy sites where content loads dynamically via JavaScript.

```
anthropic_news_blog.py, anthropic_research_blog.py, openai_research_blog.py
```

- Uses `undetected-chromedriver` to avoid bot detection
- Clicks "See more"/"Load more" button repeatedly
- Waits for content to load between clicks
- `max_clicks` safety limit to prevent infinite loops

Key functions:
- `setup_selenium_driver()` - Headless Chrome with undetected-chromedriver
- `fetch_news_content()` - Load page, click buttons, return final HTML

### When to Use Each Pattern

| Site Behavior | Pattern | Example |
|--------------|---------|---------|
| All posts on single page | Simple Static | ollama_blog.py |
| URL-based pagination (`?page=2`) | Pagination + Caching | dagster_blog.py |
| JS button loads more content | Selenium + Click | anthropic_news_blog.py |

Key libraries: `requests`, `beautifulsoup4`, `feedgen`, `selenium`, `undetected-chromedriver`

## Adding a New Feed

1. Download HTML of target blog
2. Use `@cmd_rss_feed_generator.md` prompt: `Use @cmd_rss_feed_generator.md to convert @<html>.html to a RSS feed for <url>`
3. Create `feed_generators/<source>_blog.py` following existing patterns
4. Add Make target in `makefiles/feeds.mk`
5. Update README.md table with new feed

## GitHub Actions

- `run_feeds.yml` - Runs hourly, executes `run_all_feeds.py`, commits updated XML files
- `test_feed.yml` - Tests feed generation on PRs
