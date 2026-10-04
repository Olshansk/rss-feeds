from datetime import datetime
from urllib.parse import urljoin

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from feed_history import merge_feed_history
from utils import (
    fetch_page,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "anthropic_red"
BLOG_URL = "https://www.anthropic.com/research/team/frontier-red-team"


def fetch_red_content(url=BLOG_URL):
    """Fetch content from Anthropic's red team blog."""
    try:
        return fetch_page(url)
    except Exception as e:
        logger.error(f"Error fetching red team blog content: {e!s}")
        raise


def parse_date(date_text):
    """Parse date text from article pages (e.g., 'November 12, 2025', 'September 29, 2025')."""
    date_formats = [
        "%B %d, %Y",  # November 12, 2025
        "%b %d, %Y",  # Nov 12, 2025
        "%B %Y",  # November 2025 (fallback)
        "%b %Y",  # Nov 2025 (fallback)
    ]

    for date_format in date_formats:
        try:
            date = datetime.strptime(date_text, date_format)
            return date.replace(tzinfo=pytz.UTC)
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_text}")
    return None


def parse_red_html(html_content):
    """Extract dated publication rows from the Frontier Red Team listing."""
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []
    for row in soup.select("a[href]:has(time)"):
        title = row.select_one('span[class*="__title"]')
        date = parse_date(row.find("time").get_text(" ", strip=True))
        if title is None or date is None:
            raise ValueError("Red Team publication is missing its title or date")
        articles.append(
            {
                "title": title.get_text(" ", strip=True),
                "link": urljoin(BLOG_URL, row["href"]),
                "date": date,
                "description": title.get_text(" ", strip=True),
            }
        )
    return articles


def generate_rss_feed(articles, feed_name=FEED_NAME):
    """Generate RSS feed from red team blog articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic Frontier Red Team Blog")
        fg.description(
            "Research from Anthropic's Frontier Red Team on what frontier AI models mean for national security"
        )
        setup_feed_links(fg, BLOG_URL, feed_name)
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic Frontier Red Team"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle(
            "Evidence-based analysis about AI's implications for cybersecurity, biosecurity, and autonomous systems"
        )

        # Sort articles for correct feed order (newest first in output)
        sorted_articles = sort_posts_for_feed(articles, date_field="date")

        # Add entries
        for article in sorted_articles:
            fe = fg.add_entry()
            fe.title(article["title"])
            fe.description(article["description"])
            fe.link(href=article["link"])
            fe.published(article["date"])
            fe.id(article.get("guid") or article["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {e!s}")
        raise


def main(feed_name=FEED_NAME):
    """Main function to generate RSS feed from Anthropic's red team blog."""
    try:
        # Fetch blog content
        html_content = fetch_red_content()

        # Parse articles from HTML
        articles = parse_red_html(html_content)

        if not articles:
            logger.warning("No articles found")
            return False

        articles = merge_feed_history(articles, feed_name, match_titles=True)

        # Generate RSS feed
        feed = generate_rss_feed(articles, feed_name)

        # Save feed to file
        save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {e!s}")
        return False


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
