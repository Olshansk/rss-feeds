import sys
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
    fetch_page,
    get_project_root,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    sort_posts_for_feed,
    stable_fallback_date,
)

logger = setup_logging()

FEED_NAME = "xainews"
BLOG_URL = "https://x.ai/news"


def fetch_news_content(url=BLOG_URL):
    """Fetch news content from xAI's website."""
    return fetch_page(url, timeout=10)


def parse_date(date_text):
    """Parse date from various formats used on xAI news page."""
    date_formats = [
        "%B %d, %Y",  # September 19, 2025
        "%b %d, %Y",  # Sep 19, 2025
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
    return None  # Return None so caller can use stable fallback with appropriate identifier


def extract_articles(soup):
    """Extract article information from the parsed HTML."""
    articles = []
    seen_links = set()

    # Find all article containers
    # Looking for divs with class "group relative" that contain news articles
    article_containers = soup.select("div.group.relative")

    logger.info(f"Found {len(article_containers)} potential article containers")

    for container in article_containers:
        try:
            # Extract the link and title
            title_link = container.select_one('a[href*="/news/"]')
            if not title_link:
                continue

            href = title_link.get("href", "")
            if not href:
                continue

            # Build full URL
            link = f"https://x.ai{href}" if href.startswith("/") else href

            # Skip duplicates
            if link in seen_links:
                continue

            # Skip the main news page link
            if link.endswith("/news") or link.endswith("/news/"):
                continue

            seen_links.add(link)

            # Extract title - can be in h3 or h4
            title_elem = title_link.select_one("h3, h4")
            if not title_elem:
                logger.debug(f"Could not extract title for link: {link}")
                continue

            title = title_elem.text.strip()

            # Extract description
            description_elem = container.select_one("p.text-secondary")
            description = description_elem.text.strip() if description_elem else title

            # Extract date - try multiple selectors
            date = None

            # First try: p.mono-tag.text-xs.leading-6 (featured article format)
            date_elem = container.select_one("p.mono-tag.text-xs.leading-6")
            if date_elem:
                date_text = date_elem.text.strip()
                if any(
                    month in date_text
                    for month in [
                        "January",
                        "February",
                        "March",
                        "April",
                        "May",
                        "June",
                        "July",
                        "August",
                        "September",
                        "October",
                        "November",
                        "December",
                    ]
                ):
                    date = parse_date(date_text)

            # Second try: span.mono-tag.text-xs in footer (standard article format)
            if not date:
                footer_elements = container.select(
                    "div.flex.items-center.justify-between span.mono-tag.text-xs"
                )
                for elem in footer_elements:
                    text = elem.text.strip()
                    # Check if this looks like a date
                    if any(
                        month in text
                        for month in [
                            "January",
                            "February",
                            "March",
                            "April",
                            "May",
                            "June",
                            "July",
                            "August",
                            "September",
                            "October",
                            "November",
                            "December",
                        ]
                    ):
                        date = parse_date(text)
                        break

            # Fallback: use stable date if we couldn't extract one
            if not date:
                logger.warning(f"Could not extract date for article: {title}")
                date = stable_fallback_date(link)

            # Extract category (tags like "grok", etc.)
            category = "News"
            category_elem = container.select_one(
                "div:not(.flex.items-center.justify-between) span.mono-tag.text-xs"
            )
            if category_elem:
                category_text = category_elem.text.strip().lower()
                # Skip if it's a date
                if not any(
                    month.lower() in category_text
                    for month in [
                        "january",
                        "february",
                        "march",
                        "april",
                        "may",
                        "june",
                        "july",
                        "august",
                        "september",
                        "october",
                        "november",
                        "december",
                    ]
                ):
                    category = category_text.capitalize()

            article = {
                "title": title,
                "link": link,
                "date": date,
                "category": category,
                "description": description,
            }

            articles.append(article)
            logger.debug(f"Extracted article: {title} ({date})")

        except Exception as e:
            logger.warning(f"Error parsing article container: {str(e)}")
            continue

    logger.info(f"Successfully parsed {len(articles)} articles")
    return articles


def parse_news_html(html_content):
    """Parse the news HTML content and extract article information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        return extract_articles(soup)
    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(articles):
    """Generate RSS feed from news articles."""
    try:
        fg = FeedGenerator()
        fg.title("xAI News")
        fg.description("Latest news and updates from xAI")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "xAI"})
        fg.subtitle("Latest updates from xAI")
        setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

        # Sort articles for correct feed order (newest first in output)
        articles_sorted = sort_posts_for_feed(articles, date_field="date")

        # Add entries
        for article in articles_sorted:
            fe = fg.add_entry()
            fe.title(article["title"])
            fe.description(article["description"])
            fe.link(href=article["link"])
            fe.published(article["date"])
            fe.category(term=article["category"])
            fe.id(article["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def main(full_reset=False, html_file=None):
    """Main function to generate RSS feed from xAI's news page.

    Args:
        full_reset: Unused, kept for interface consistency.
        html_file: Optional path to local HTML file to parse instead of fetching from web
    """
    try:
        # Get HTML content either from local file or web
        if html_file:
            logger.info(f"Reading HTML content from local file: {html_file}")
            with open(html_file, "r", encoding="utf-8") as f:
                html_content = f.read()
        else:
            # Fetch news content from web
            html_content = fetch_news_content()

        # Parse articles from HTML
        articles = parse_news_html(html_content)

        if not articles:
            logger.warning("No articles found!")
            return False

        # Generate RSS feed with all articles
        feed = generate_rss_feed(articles)

        # Save feed to file
        save_rss_feed(feed, FEED_NAME)

        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    from pathlib import Path

    # Check if HTML file path was provided as argument
    html_file = None
    if len(sys.argv) > 1:
        html_file = sys.argv[1]
        if not Path(html_file).exists():
            logger.error(f"HTML file not found: {html_file}")
            sys.exit(1)

    # Check if xAINews.html exists in current directory or parent directory
    if not html_file:
        potential_paths = [
            Path("xAINews.html"),
            Path("../xAINews.html"),
            get_project_root() / "xAINews.html",
        ]
        for path in potential_paths:
            if path.exists():
                html_file = str(path)
                logger.info(f"Found local HTML file: {html_file}")
                break

    main(html_file=html_file)
