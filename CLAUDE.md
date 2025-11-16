# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

RSS feed generator that creates RSS feeds for blogs that don't provide them.
Uses Python scripts to scrape blog websites and convert to RSS XML feeds, with automated hourly updates via GitHub Actions.

## Development Commands

### Environment Setup

```bash
# Create and activate virtual environment
make env_create
$(make env_source)  # Run the output of this command

# Install dependencies
make env_install
```

### Feed Generation

```bash
# Generate all RSS feeds
make feeds_generate_all

# Generate specific feed (examples)
make feeds_anthropic_news
make feeds_openai_research
make feeds_paulgraham
```

### Code Quality

```bash
# Format Python code (black + isort)
make dev_format
```

### Testing

```bash
# Test feed generation workflow locally (requires 'act' tool)
make ci_test_workflow_local

# Run test feed generator
make dev_test_feed
```

## Architecture

### Feed Generation Pattern

Each feed generator script in `feed_generators/` follows this pattern:

1. **Fetch**: HTTP request to blog URL (using `requests` or `selenium` for JavaScript-rendered content)
2. **Parse**: Extract article data using BeautifulSoup with CSS selectors
3. **Generate**: Create RSS XML using `feedgen` library
4. **Save**: Write to `feeds/feed_*.xml`

Common utilities per feed generator:

- Helper functions: `get_project_root()`, `ensure_feeds_directory()`
- Robust selector fallbacks for title/description/date extraction
- Timezone handling with `pytz` (typically UTC)

### Orchestration Flow

```
run_all_feeds.py → Discovers all *.py files in feed_generators/
                 → Runs each script via subprocess
                 → Logs success/failure summary
```

GitHub Actions workflow (`.github/workflows/run_feeds.yml`):

- Runs hourly via cron
- Sets up Python 3.11 + Chrome for Selenium
- Installs dependencies with `uv`
- Executes `feed_generators/run_all_feeds.py`
- Auto-commits updated XML files

### Makefile Organization

Modular makefile structure in `makefiles/`:

- `env.mk`: Virtual environment management
- `feeds.mk`: Individual feed generation targets
- `dev.mk`: Development tools (formatting, testing)
- `ci.mk`: CI/CD workflow testing
- `common.mk`: Shared utilities and helpers
- `colors.mk`: Terminal color definitions

Legacy target aliases in main `Makefile` maintain backwards compatibility.

## Adding New Feeds

1. Create `feed_generators/{name}_blog.py` following existing pattern
2. Add make target to `makefiles/feeds.mk`
3. Script will be auto-discovered by `run_all_feeds.py`
4. GitHub Actions will run it hourly
5. (Optional) Use `/rss_feed_generator` slash command in Claude Code CLI with downloaded HTML as starting point

### Key Dependencies

- `beautifulsoup4` & `bs4`: HTML parsing
- `feedgen`: RSS XML generation
- `requests`: HTTP requests
- `selenium` & `undetected-chromedriver`: JavaScript-rendered content
- `python-dateutil` & `pytz`: Date/time handling
