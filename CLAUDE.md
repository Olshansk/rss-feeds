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
makefiles/                 # Modular Makefile includes (feeds.mk, env.mk, dev.mk, ci.mk)
```

### Feed Generator Pattern

Each generator follows a consistent structure:
1. `fetch_blog_content(url)` - HTTP request with User-Agent header
2. `parse_blog_html(html)` - BeautifulSoup parsing for posts (title, date, description, link)
3. `generate_rss_feed(posts)` - Create feed using `feedgen` library
4. `save_rss_feed(fg, name)` - Write to `feeds/feed_{name}.xml`

Key libraries: `requests`, `beautifulsoup4`, `feedgen`, `selenium` (for JS-heavy sites)

## Adding a New Feed

1. Download HTML of target blog
2. Use `@cmd_rss_feed_generator.md` prompt: `Use @cmd_rss_feed_generator.md to convert @<html>.html to a RSS feed for <url>`
3. Create `feed_generators/<source>_blog.py` following existing patterns
4. Add Make target in `makefiles/feeds.mk`
5. Update README.md table with new feed

## GitHub Actions

- `run_feeds.yml` - Runs hourly, executes `run_all_feeds.py`, commits updated XML files
- `test_feed.yml` - Tests feed generation on PRs
