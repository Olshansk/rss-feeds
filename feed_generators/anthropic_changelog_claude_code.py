import logging
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytz
import requests
from feedgen.feed import FeedGenerator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_project_root():
    return Path(__file__).parent.parent


def ensure_feeds_directory():
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def fetch_changelog_content(
    url="https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md",
):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching changelog content: {str(e)}")
        raise


def version_to_date(version_str):
    """Convert version string to a stable date based on version number.

    This ensures each version always gets the same date regardless of
    its position in the changelog file.
    """
    try:
        parts = version_str.split(".")
        major = int(parts[0]) if len(parts) > 0 else 0
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        # Calculate days from epoch: higher versions = later dates
        days_offset = major * 1000 + minor * 100 + patch
        epoch = datetime(2020, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)
        return epoch + timedelta(days=days_offset)
    except (ValueError, IndexError):
        return datetime(2024, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)


def parse_changelog_markdown(markdown_content):
    try:
        items = []
        lines = markdown_content.split("\n")
        current_version = None
        current_changes = []

        for line in lines:
            line = line.strip()

            # Check for version headers (## 1.0.71, ## 1.0.70, etc.)
            if line.startswith("## ") and re.match(r"## \d+\.\d+\.\d+", line):
                # Save previous version if exists
                if current_version and current_changes:
                    version_anchor = current_version.replace(".", "")
                    # Create HTML list for description
                    description_html = (
                        "<ul>"
                        + "".join(f"<li>{change}</li>" for change in current_changes)
                        + "</ul>"
                    )
                    items.append(
                        {
                            "title": f"v{current_version}",
                            "link": f"https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#{version_anchor}",
                            "description": description_html,
                            "date": version_to_date(current_version),
                            "category": "Changelog",
                        }
                    )

                # Start new version
                current_version = line[3:].strip()  # Remove "## "
                current_changes = []
                continue

            # Check for bullet points under a version
            if current_version and line.startswith("- "):
                change_description = line[2:].strip()  # Remove "- "
                if change_description:
                    current_changes.append(change_description)

        # Don't forget the last version
        if current_version and current_changes:
            version_anchor = current_version.replace(".", "")
            description_html = (
                "<ul>"
                + "".join(f"<li>{change}</li>" for change in current_changes)
                + "</ul>"
            )
            items.append(
                {
                    "title": f"v{current_version}",
                    "link": f"https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md#{version_anchor}",
                    "description": description_html,
                    "date": version_to_date(current_version),
                    "category": "Changelog",
                }
            )

        logger.info(f"Successfully parsed {len(items)} changelog items")
        return items

    except Exception as e:
        logger.error(f"Error parsing markdown content: {str(e)}")
        raise


def generate_rss_feed(items, feed_name="anthropic_changelog_claude_code"):
    try:
        fg = FeedGenerator()
        fg.title("Claude Code Changelog")
        fg.description("Version updates and changes from Claude Code CHANGELOG.md")
        fg.link(href="https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md")
        fg.language("en")

        fg.author({"name": "Anthropic"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Claude Code Changelog")
        fg.link(
            href="https://github.com/anthropics/claude-code/blob/main/CHANGELOG.md",
            rel="alternate",
        )
        fg.link(href=f"https://anthropic.com/feed_{feed_name}.xml", rel="self")

        items.sort(key=lambda x: x["date"], reverse=True)

        for item in items:
            fe = fg.add_entry()
            fe.title(item["title"])
            fe.description(item["description"])
            fe.link(href=item["link"])
            fe.published(item["date"])
            fe.category(term=item["category"])
            # Use stable GUID based on version link only (not hash which could vary)
            fe.id(item["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def save_rss_feed(feed_generator, feed_name="anthropic_changelog_claude_code"):
    try:
        feeds_dir = ensure_feeds_directory()
        output_filename = feeds_dir / f"feed_{feed_name}.xml"
        feed_generator.rss_file(str(output_filename), pretty=True)
        logger.info(f"Successfully saved RSS feed to {output_filename}")
        return output_filename
    except Exception as e:
        logger.error(f"Error saving RSS feed: {str(e)}")
        raise


def main(feed_name="anthropic_changelog_claude_code"):
    try:
        markdown_content = fetch_changelog_content()
        items = parse_changelog_markdown(markdown_content)

        if not items:
            logger.warning("No changelog items found")
            return False

        feed = generate_rss_feed(items, feed_name)
        output_file = save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(items)} items")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
