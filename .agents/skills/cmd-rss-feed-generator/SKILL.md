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
  - [Step 1: Review Existing Feed Generators](#step-1-review-existing-feed-generators)
  - [Step 2: Analyze the Blog Source](#step-2-analyze-the-blog-source)
  - [Step 3: Create the Feed Generator Script](#step-3-create-the-feed-generator-script)
  - [Step 4: Add Makefile Target](#step-4-add-makefile-target)
  - [Step 5: Test the Feed Generator](#step-5-test-the-feed-generator)
  - [Step 6: Integration Checklist](#step-6-integration-checklist)
- [Common Patterns](#common-patterns)
  - [Dynamic Content (JavaScript-rendered)](#dynamic-content-javascript-rendered)
  - [Multiple Feed Types](#multiple-feed-types)
  - [Incremental Updates](#incremental-updates)
- [Troubleshooting](#troubleshooting)
  - [No articles found](#no-articles-found)
  - [Date parsing failures](#date-parsing-failures)
  - [Blocked requests (403/429 errors)](#blocked-requests-403429-errors)

## Project Context

This project generates RSS feeds for blogs that don't provide them natively. The system uses:

- Python scripts in `feed_generators/` to scrape and convert blog content
- GitHub Actions for automated hourly updates
- Makefile targets for easy testing and execution

## Workflow

### Step 1: Review Existing Feed Generators

**Always start by examining existing feed generators as references:**

```bash
ls feed_generators/*.py
```

Recommended references:

- `anthropic_news_blog.py` - Clean structure, robust error handling
- `xainews_blog.py` - Local file fallback support, multiple date formats
- `ollama_blog.py` - Simple implementation
- `blogsurgeai_feed_generator.py` - Dynamic content with Selenium

Study these to understand:

- Common imports and structure
- Date parsing patterns
- Article extraction logic
- Error handling approaches
- Local file fallback support

### Step 2: Analyze the Blog Source

When given an HTML file or website URL:

1. **Examine the HTML structure** to identify:

   - Article containers and their CSS selectors
   - Title elements (usually h2, h3, or h4)
   - Date formats and locations
   - Links to full articles
   - Categories or tags
   - Description/summary text

2. **Handle access issues**:
   - If the site blocks automated requests, work with a local HTML file first
   - The user can provide HTML via browser's "Save Page As" feature
   - Support both local file and web fetching modes in the final script

### Step 3: Create the Feed Generator Script

Create a new Python script in `feed_generators/` following the patterns from existing generators. Your script should include:

**Required Functions:**

- `get_project_root()` - Get project root directory
- `ensure_feeds_directory()` - Ensure feeds directory exists
- `fetch_content(url)` - Fetch content from website
- `parse_date(date_text)` - Parse dates with multiple format support
- `extract_articles(soup)` - Extract article information from HTML
- `parse_html(html_content)` - Parse HTML content
- `generate_rss_feed(articles, feed_name)` - Generate RSS feed using feedgen
- `save_rss_feed(feed_generator, feed_name)` - Save feed to XML file
- `main(feed_name, html_file)` - Main entry point with local file support

**Key Implementation Details:**

- **Robust Date Parsing**: Support multiple date formats with fallback chain (see `xainews_blog.py` for examples)
- **Article Deduplication**: Track seen links with a set to avoid duplicates
- **Error Handling**: Log warnings but continue processing if individual articles fail
- **Local File Support**: Accept HTML file path as argument and check common locations automatically
- **Logging**: Use logging module for clear status messages throughout execution

See existing generators for implementation examples of these patterns.

### Step 4: Add Makefile Target

Add a new target to `makefiles/feeds.mk` following the existing pattern:

```makefile
.PHONY: feeds_new_site
feeds_new_site: ## Generate RSS feed for NewSite
   $(call check_venv)
   $(call print_info,Generating NewSite feed)
   $(Q)uv run feed_generators/new_site_blog.py
   $(call print_success,NewSite feed generated)
```

Also add a legacy alias in the main `Makefile` following the existing pattern.

### Step 5: Test the Feed Generator

1. **Test with local HTML** (if site blocks requests):

   ```bash
   uv run feed_generators/new_site_blog.py blog.html
   ```

2. **Test with Makefile**:

   ```bash
   make feeds_new_site
   ```

3. **Validate the generated feed**:

   ```bash
   ls -la feeds/feed_new_site.xml
   head -50 feeds/feed_new_site.xml
   ```

### Step 6: Integration Checklist

- [ ] Script follows naming pattern: `new_site_blog.py`
- [ ] Output file follows pattern: `feed_new_site.xml`
- [ ] Makefile target added to `makefiles/feeds.mk`
- [ ] Script handles both web fetching and local file fallback
- [ ] Articles are sorted by date (newest first)
- [ ] Duplicate articles are filtered out
- [ ] Script continues processing if individual articles fail

## Common Patterns

### Dynamic Content (JavaScript-rendered)

- See `blogsurgeai_feed_generator.py` for Selenium/undetected-chromedriver example.

### Multiple Feed Types

- See Anthropic generators (`anthropic_news_blog.py`, `anthropic_eng_blog.py`, `anthropic_research_blog.py`) for examples of handling multiple sections from the same site.

### Incremental Updates

- See `anthropic_news_blog.py` for the `get_existing_links_from_feed()` pattern to avoid re-processing articles.

## Troubleshooting

### No articles found

- Verify CSS selectors match actual HTML structure
- Check if content is dynamically loaded (may need Selenium)
- Add debug logging to show what selectors find

### Date parsing failures

- Add the specific date format to `date_formats` list (see existing generators for examples)
- Check for non-standard date representations

### Blocked requests (403/429 errors)

- Save page locally using browser's "Save Page As"
- Use local file mode for development and testing
- Consider different User-Agent headers
