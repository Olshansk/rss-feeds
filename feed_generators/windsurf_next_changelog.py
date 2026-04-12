import re
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from utils import (fetch_page, save_rss_feed, setup_feed_links, setup_logging,
                   sort_posts_for_feed)

logger = setup_logging()

FEED_NAME = "windsurf_next_changelog"
BLOG_URL = "https://windsurf.com/changelog/windsurf-next"


def fetch_changelog_content(url=BLOG_URL):
    """Fetch changelog content from Windsurf Next's website."""
    try:
        return fetch_page(url)
    except Exception as e:
        logger.error(f"Error fetching changelog content: {str(e)}")
        raise


def parse_date(date_text):
    """Parse date from various formats used on Windsurf changelog."""
    date_formats = [
        "%B %d, %Y",  # November 25, 2025
        "%b %d, %Y",  # Nov 25, 2025
        "%B %d %Y",
        "%b %d %Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ]

    date_text = date_text.strip()
    for date_format in date_formats:
        try:
            date = datetime.strptime(date_text, date_format)
            return date.replace(tzinfo=pytz.UTC)
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_text}")
    return None


def parse_changelog_html(html_content):
    """Parse the changelog HTML content and extract version entries."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        changelog_entries = []

        # Version pattern to find elements with version IDs
        version_pattern = re.compile(r"^\d+\.\d+\.\d+$")

        # Find all elements with version-like IDs
        version_elements = soup.find_all(id=version_pattern)

        for elem in version_elements:
            version = elem.get("id")
            elem_text = elem.get_text()

            # Extract date from the element's text
            date_match = re.search(
                r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
                elem_text,
            )

            if date_match:
                date = parse_date(date_match.group())
            else:
                logger.warning(f"Could not find date for version {version}")
                date = datetime.now(pytz.UTC)

            # Extract description from the prose/article content as HTML
            prose_elem = elem.select_one(".prose")
            if prose_elem:
                # Get inner HTML, excluding images
                description_parts = []
                for child in prose_elem.children:
                    if child.name == "img":
                        continue
                    if child.name == "h1":
                        # Major section header (AI Models, Features & Tools, etc.)
                        heading_text = child.get_text(strip=True)
                        description_parts.append(f"<h3>{heading_text}</h3>")
                    elif child.name in ["h2", "h3"]:
                        # Subheading (Gemini 3 Pro, SWE-1.5, etc.)
                        heading_text = child.get_text(strip=True)
                        description_parts.append(
                            f"<p><strong>{heading_text}</strong></p>"
                        )
                    elif child.name == "p":
                        description_parts.append(f"<p>{child.get_text(strip=True)}</p>")
                    elif child.name == "ul":
                        items = [
                            f"<li>{li.get_text(strip=True)}</li>"
                            for li in child.find_all("li")
                        ]
                        description_parts.append(f"<ul>{''.join(items)}</ul>")
                description = "".join(description_parts)
            else:
                # Fallback: extract text with separator
                description = elem_text
                if date_match:
                    description = elem_text[date_match.end() :].strip()

            # Limit length
            if len(description) > 2000:
                description = description[:2000] + "..."

            if not description:
                description = f"Version {version} release"

            # Create link with anchor
            link = f"https://windsurf.com/changelog/windsurf-next#{version}"

            changelog_entries.append(
                {
                    "title": f"Windsurf Next {version}",
                    "version": version,
                    "link": link,
                    "description": description,
                    "date": date,
                }
            )

        logger.info(f"Successfully parsed {len(changelog_entries)} changelog entries")
        return changelog_entries

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(changelog_entries, feed_name=FEED_NAME):
    """Generate RSS feed from changelog entries."""
    try:
        fg = FeedGenerator()
        fg.title("Windsurf Next Changelog")
        fg.description("Version updates and changes from Windsurf Next")
        setup_feed_links(fg, BLOG_URL, feed_name)
        fg.language("en")

        fg.author({"name": "Windsurf"})
        fg.subtitle("Latest version updates from Windsurf Next")

        # Sort for correct feed order (newest first in output)
        entries_sorted = sort_posts_for_feed(changelog_entries, date_field="date")

        for entry in entries_sorted:
            fe = fg.add_entry()
            fe.title(entry["title"])
            fe.description(entry["description"])
            fe.link(href=entry["link"])
            fe.published(entry["date"])
            fe.category(term="Changelog")
            fe.id(f"{entry['link']}#{entry['version']}")

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def main(feed_name=FEED_NAME):
    """Main function to generate RSS feed from Windsurf Next changelog."""
    try:
        html_content = fetch_changelog_content()
        changelog_entries = parse_changelog_html(html_content)

        if not changelog_entries:
            logger.warning("No changelog entries found!")
            return False

        feed = generate_rss_feed(changelog_entries, feed_name)
        save_rss_feed(feed, feed_name)

        logger.info(
            f"Successfully generated RSS feed with {len(changelog_entries)} entries"
        )
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
