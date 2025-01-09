import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path

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


def fetch_news_content(url="https://www.anthropic.com/news"):
    """Fetch news content from Anthropic's website."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching news content: {str(e)}")
        raise


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


def generate_rss_feed(articles, feed_name="anthropic"):
    """Generate RSS feed from news articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic News")
        fg.description("Latest news and updates from Anthropic")
        fg.link(href="https://www.anthropic.com/news")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Latest updates from Anthropic's newsroom")
        fg.link(href="https://www.anthropic.com/news", rel="alternate")
        fg.link(href=f"https://anthropic.com/news/feed_{feed_name}.xml", rel="self")

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


def save_rss_feed(feed_generator, feed_name="anthropic"):
    """Save the RSS feed to a file in the feeds directory."""
    try:
        # Ensure feeds directory exists and get its path
        feeds_dir = ensure_feeds_directory()

        # Create the output file path
        output_filename = feeds_dir / f"feed_{feed_name}.xml"

        # Save the feed
        feed_generator.rss_file(str(output_filename), pretty=True)
        logger.info(f"Successfully saved RSS feed to {output_filename}")
        return output_filename

    except Exception as e:
        logger.error(f"Error saving RSS feed: {str(e)}")
        raise


def main(feed_name="anthropic"):
    """Main function to generate RSS feed from Anthropic's news page."""
    try:
        # Fetch news content
        html_content = fetch_news_content()

        # Parse articles from HTML
        articles = parse_news_html(html_content)

        # Generate RSS feed
        feed = generate_rss_feed(articles, feed_name)

        # Save feed to file
        output_file = save_rss_feed(feed, feed_name)

        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
