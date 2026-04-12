import re
from datetime import datetime

import pytz
from feedgen.feed import FeedGenerator
from utils import fetch_page, save_rss_feed, setup_feed_links, setup_logging

logger = setup_logging()

FEED_NAME = "anthropic_changelog_claude_code"
BLOG_URL = "https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md"


def fetch_changelog_content(
    url="https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md",
):
    try:
        return fetch_page(url)
    except Exception as e:
        logger.error(f"Error fetching changelog content: {str(e)}")
        raise


def parse_changelog_markdown(markdown_content, max_versions=50):
    try:
        items = []
        lines = markdown_content.split("\n")
        current_version = None
        current_date = None
        current_changes = []

        for line in lines:
            line = line.strip()

            # Check for version headers (## 1.0.71, ## 1.0.70, etc.)
            # Also match headers with dates like "## 1.0.71 (2025-06-15)"
            version_match = re.match(r"## (\d+\.\d+\.\d+)(?:\s*\(([^)]+)\))?", line)
            if version_match:
                # Save previous version if exists
                if current_version and current_changes:
                    version_anchor = current_version.replace(".", "")
                    # Create HTML list for description
                    description_html = (
                        "<ul>"
                        + "".join(f"<li>{change}</li>" for change in current_changes)
                        + "</ul>"
                    )
                    item = {
                        "title": f"v{current_version}",
                        "link": f"https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#{version_anchor}",
                        "description": description_html,
                        "category": "Changelog",
                    }
                    if current_date:
                        item["date"] = current_date
                    items.append(item)
                    if len(items) >= max_versions:
                        break

                # Start new version
                current_version = version_match.group(1)
                current_date = None
                date_str = version_match.group(2)
                if date_str:
                    try:
                        current_date = datetime.strptime(
                            date_str.strip(), "%Y-%m-%d"
                        ).replace(tzinfo=pytz.UTC)
                    except ValueError:
                        logger.warning(
                            f"Could not parse date '{date_str}' for version {current_version}"
                        )
                current_changes = []
                continue

            # Check for bullet points under a version
            if current_version and line.startswith("- "):
                change_description = line[2:].strip()  # Remove "- "
                if change_description:
                    current_changes.append(change_description)

        # Don't forget the last version (if we haven't hit the limit)
        if current_version and current_changes and len(items) < max_versions:
            version_anchor = current_version.replace(".", "")
            description_html = (
                "<ul>"
                + "".join(f"<li>{change}</li>" for change in current_changes)
                + "</ul>"
            )
            item = {
                "title": f"v{current_version}",
                "link": f"https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#{version_anchor}",
                "description": description_html,
                "category": "Changelog",
            }
            if current_date:
                item["date"] = current_date
            items.append(item)

        logger.info(f"Successfully parsed {len(items)} changelog items")
        return items

    except Exception as e:
        logger.error(f"Error parsing markdown content: {str(e)}")
        raise


def generate_rss_feed(items, feed_name=FEED_NAME):
    try:
        fg = FeedGenerator()
        fg.title("Claude Code Changelog")
        fg.description("Version updates and changes from Claude Code CHANGELOG.md")
        setup_feed_links(fg, BLOG_URL, feed_name)
        fg.language("en")

        fg.author({"name": "Anthropic"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Claude Code Changelog")

        # feedgen reverses order, so reverse items to maintain newest-first
        for item in reversed(items):
            fe = fg.add_entry()
            fe.title(item["title"])
            fe.description(item["description"])
            fe.link(href=item["link"])
            if item.get("date"):
                fe.published(item["date"])
            fe.category(term=item["category"])
            fe.id(item["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def main(feed_name=FEED_NAME):
    try:
        markdown_content = fetch_changelog_content()
        items = parse_changelog_markdown(markdown_content)

        if not items:
            logger.warning("No changelog items found")
            return False

        feed = generate_rss_feed(items, feed_name)
        save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(items)} items")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
