from feedgen.feed import FeedGenerator

from changelog import parse_changelog
from feed_history import merge_feed_history
from utils import (
    fetch_page,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "windsurf_changelog"
BLOG_URL = "https://docs.devin.ai/desktop/changelog"


def fetch_changelog_content(url=BLOG_URL):
    """Fetch changelog content from Windsurf's website."""
    try:
        return fetch_page(url)
    except Exception as e:
        logger.error(f"Error fetching changelog content: {e!s}")
        raise


def parse_changelog_html(html_content):
    """Parse the stable channel with the common changelog rules."""
    return parse_changelog(html_content, BLOG_URL, "Windsurf", "https://windsurf.com/changelog")


def generate_rss_feed(changelog_entries, feed_name=FEED_NAME):
    """Generate RSS feed from changelog entries."""
    try:
        fg = FeedGenerator()
        fg.title("Windsurf Changelog")
        fg.description("Version updates and changes from Windsurf")
        setup_feed_links(fg, BLOG_URL, feed_name)
        fg.language("en")

        fg.author({"name": "Windsurf"})
        fg.subtitle("Latest version updates from Windsurf")

        # Sort for correct feed order (newest first in output)
        entries_sorted = sort_posts_for_feed(changelog_entries, date_field="date")

        for entry in entries_sorted:
            fe = fg.add_entry()
            fe.title(entry["title"])
            fe.description(entry["description"])
            fe.link(href=entry["link"])
            fe.published(entry["date"])
            fe.category(term="Changelog")
            fe.id(entry["guid"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {e!s}")
        raise


def main(feed_name=FEED_NAME):
    """Main function to generate RSS feed from Windsurf changelog."""
    try:
        html_content = fetch_changelog_content()
        changelog_entries = parse_changelog_html(html_content)

        if not changelog_entries:
            logger.warning("No changelog entries found!")
            return False

        changelog_entries = merge_feed_history(changelog_entries, feed_name)
        feed = generate_rss_feed(changelog_entries, feed_name)
        save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(changelog_entries)} entries")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {e!s}")
        return False


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
