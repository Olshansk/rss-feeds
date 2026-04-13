# Contributing

## Dev Setup

```bash
uv sync --group dev
pre-commit install
```

## Running Feeds

Run all request-based feeds:

```bash
uv run feed_generators/run_all_feeds.py --skip-selenium
```

Run a single feed:

```bash
uv run feed_generators/ollama_blog.py
uv run feed_generators/dagster_blog.py --full  # full reset (all pages)
```

## Code Style

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting, enforced via pre-commit hooks.

```bash
ruff check .              # lint
ruff check --fix .        # lint + auto-fix
ruff format .             # format
```

Or via Make:

```bash
make dev_lint             # check only
make dev_lint_fix         # auto-fix + format
```

## Adding a New Feed

See [AGENTS.md](./AGENTS.md) for the complete guide on creating feed generators.

**Recommended workflow**: Use [Claude Code](https://claude.com/claude-code) with the [Playwright MCP](https://github.com/microsoft/playwright-mcp) to inspect the target site, understand its structure, and generate the scraper.

**When to write a custom scraper**: Only if the site has no official RSS feed, or if a custom parser adds significant value over the official feed (e.g., full content extraction, structured metadata). Simple filtering (e.g., category-only views) does not justify a custom scraper. Check the README for sites that already have official feeds.

## Pull Requests

1. Branch from `main`
2. Follow the existing generator patterns in `feed_generators/`
3. Test your feed locally before submitting
4. Reference any related issues in the PR description
