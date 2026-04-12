from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import (
    fetch_page,
    save_rss_feed,
    setup_feed_links,
    setup_logging,
)

logger = setup_logging()

FEED_NAME = "anthropic"
BLOG_URL = "https://www.anthropic.com/news"


def parse_news_html(html_content):
    """Parse the news HTML content and extract article information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        articles = []

        # Find all article cards
        news_cards = soup.select("a.PostCard_post-card__z_Sqq")

        for card in news_cards:
            # Extract title
            title_elem = card.select_one("h3.PostCard_post-heading__Ob1pu")
            if not title_elem:
                continue
            title = title_elem.text.strip()

            # Extract link
            link = "https://www.anthropic.com" + card["href"] if card["href"].startswith("/") else card["href"]

            # Extract date
            date_elem = card.select_one("div.PostList_post-date__djrOA")
            if date_elem:
                try:
                    date = datetime.strptime(date_elem.text.strip(), "%b %d, %Y")
                    date = date.replace(tzinfo=pytz.UTC)
                except ValueError:
                    logger.warning(f"Could not parse date for article: {title}")
                    date = datetime.now(pytz.UTC)
            else:
                date = datetime.now(pytz.UTC)

            # Extract category
            category_elem = card.select_one("span.text-label")
            category = category_elem.text.strip() if category_elem else "News"

            # Extract description (if present in the HTML)
            # Note: Description might not be directly available, using title as fallback
            description = title

            articles.append(
                {"title": title, "link": link, "date": date, "category": category, "description": description}
            )

        logger.info(f"Successfully parsed {len(articles)} articles")
        return articles

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(articles):
    """Generate RSS feed from news articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic News")
        fg.description("Latest news and updates from Anthropic")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Latest updates from Anthropic's newsroom")
        setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

        # Add entries
        for article in articles:
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


def get_existing_links_from_feed(feed_path):
    """Parse the existing RSS feed and return a set of all article links."""
    import xml.etree.ElementTree as ET

    existing_links = set()
    try:
        if not feed_path.exists():
            return existing_links
        tree = ET.parse(feed_path)
        root = tree.getroot()
        # RSS 2.0: items under channel/item
        for item in root.findall("./channel/item"):
            link_elem = item.find("link")
            if link_elem is not None and link_elem.text:
                existing_links.add(link_elem.text.strip())
    except Exception as e:
        logger.warning(f"Failed to parse existing feed for deduplication: {str(e)}")
    return existing_links


def main():
    """Main function to generate RSS feed from Anthropic's news page."""
    try:
        # Fetch news content
        html_content = fetch_page(BLOG_URL)

        # Parse articles from HTML
        articles = parse_news_html(html_content)

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
    main()
