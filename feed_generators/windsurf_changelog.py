import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path
import re

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def ensure_feeds_directory():
    """Ensure the feeds directory exists."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def fetch_changelog_content(url="https://windsurf.com/changelog"):
    """Fetch changelog content from Windsurf's website."""
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
        version_pattern = re.compile(r'^\d+\.\d+\.\d+$')

        # Find all elements with version-like IDs
        version_elements = soup.find_all(id=version_pattern)

        for elem in version_elements:
            version = elem.get("id")
            elem_text = elem.get_text()

            # Extract date from the element's text
            date_match = re.search(
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
                elem_text
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
                        description_parts.append(f"<p><strong>{heading_text}</strong></p>")
                    elif child.name == "p":
                        description_parts.append(f"<p>{child.get_text(strip=True)}</p>")
                    elif child.name == "ul":
                        items = [f"<li>{li.get_text(strip=True)}</li>" for li in child.find_all("li")]
                        description_parts.append(f"<ul>{''.join(items)}</ul>")
                description = "".join(description_parts)
            else:
                # Fallback: extract text with separator
                description = elem_text
                if date_match:
                    description = elem_text[date_match.end():].strip()

            # Limit length
            if len(description) > 2000:
                description = description[:2000] + "..."

            if not description:
                description = f"Version {version} release"

            # Create link with anchor
            link = f"https://windsurf.com/changelog#{version}"

            changelog_entries.append({
                "title": f"Windsurf {version}",
                "version": version,
                "link": link,
                "description": description,
                "date": date,
            })

        logger.info(f"Successfully parsed {len(changelog_entries)} changelog entries")
        return changelog_entries

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(changelog_entries, feed_name="windsurf_changelog"):
    """Generate RSS feed from changelog entries."""
    try:
        fg = FeedGenerator()
        fg.title("Windsurf Changelog")
        fg.description("Version updates and changes from Windsurf")
        fg.link(href="https://windsurf.com/changelog")
        fg.language("en")

        fg.author({"name": "Windsurf"})
        fg.subtitle("Latest version updates from Windsurf")
        fg.link(href="https://windsurf.com/changelog", rel="alternate")
        fg.link(href=f"https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_{feed_name}.xml", rel="self")

        # Sort by date (newest first)
        entries_sorted = sorted(changelog_entries, key=lambda x: x["date"], reverse=True)

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


def save_rss_feed(feed_generator, feed_name="windsurf_changelog"):
    """Save the RSS feed to a file in the feeds directory."""
    try:
        feeds_dir = ensure_feeds_directory()
        output_filename = feeds_dir / f"feed_{feed_name}.xml"
        feed_generator.rss_file(str(output_filename), pretty=True)
        logger.info(f"Successfully saved RSS feed to {output_filename}")
        return output_filename
    except Exception as e:
        logger.error(f"Error saving RSS feed: {str(e)}")
        raise


def main(feed_name="windsurf_changelog"):
    """Main function to generate RSS feed from Windsurf changelog."""
    try:
        html_content = fetch_changelog_content()
        changelog_entries = parse_changelog_html(html_content)

        if not changelog_entries:
            logger.warning("No changelog entries found!")
            return False

        feed = generate_rss_feed(changelog_entries, feed_name)
        output_file = save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(changelog_entries)} entries")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
