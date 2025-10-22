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


def fetch_content(url):
    """Fetch content from the given URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching content: {str(e)}")
        raise


def extract_title(card):
    """Extract title using multiple fallback selectors."""
    selectors = [
        "h2.article-title",
        "h2",
        "h3",
        "h3",
        "h2",
        "h1",
    ]
    for selector in selectors:
        elem = card.select_one(selector)
        if elem and elem.text.strip():
            return elem.text.strip()
    return None


def extract_date(card):
    """Extract date using multiple fallback selectors and formats."""
    selectors = [
        "time",
        ".date",
        "time",
        "span[class*='date']",
        "div[class*='date']",
    ]

    date_formats = [
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
    ]

    for selector in selectors:
        elem = card.select_one(selector)
        if elem:
            date_text = elem.text.strip()
            # Try datetime attribute first (for <time> tags)
            datetime_attr = elem.get('datetime')
            if datetime_attr:
                try:
                    date = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00'))
                    return date.replace(tzinfo=pytz.UTC)
                except ValueError:
                    pass

            # Try parsing text content
            for date_format in date_formats:
                try:
                    date = datetime.strptime(date_text, date_format)
                    return date.replace(tzinfo=pytz.UTC)
                except ValueError:
                    continue

    # If no date found, use current date
    return datetime.now(pytz.UTC)


def extract_description(card):
    """Extract description/excerpt from the card."""
    selectors = [
        "p.article-summary",
        "p",
        "p",
        "div.excerpt",
        ".summary",
    ]
    for selector in selectors:
        elem = card.select_one(selector)
        if elem and elem.text.strip():
            return elem.text.strip()
    return ""


def extract_link(card, base_url):
    """Extract link from the card."""
    # Try to find a link in the card
    link_elem = card if card.name == 'a' else card.select_one('a')
    if link_elem:
        href = link_elem.get('href', '')
        if href:
            # Build full URL
            if href.startswith('/'):
                return base_url.rstrip('/') + href
            elif href.startswith('http'):
                return href
            else:
                return base_url.rstrip('/') + '/' + href
    return None


def validate_article(article):
    """Validate that article has all required fields."""
    if not article.get("title") or len(article["title"]) < 3:
        logger.warning(f"Invalid title for article: {article.get('link', 'unknown')}")
        return False

    if not article.get("link") or not article["link"].startswith("http"):
        logger.warning(f"Invalid link for article: {article.get('title', 'unknown')}")
        return False

    if not article.get("date"):
        logger.warning(f"Missing date for article: {article.get('title', 'unknown')}")
        return False

    return True


def parse_html(html_content, base_url):
    """Parse the HTML content and extract article information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        articles = []
        seen_links = set()

        # Find all article elements using detected selector
        all_cards = soup.select('article')

        logger.info(f"Found {len(all_cards)} potential articles")

        for card in all_cards:
            # Extract link
            link = extract_link(card, base_url)
            if not link:
                continue

            # Skip duplicates
            if link in seen_links:
                continue
            seen_links.add(link)

            # Extract title
            title = extract_title(card)
            if not title:
                continue

            # Extract date
            date = extract_date(card)

            # Extract description
            description = extract_description(card)

            article = {
                "title": title,
                "link": link,
                "date": date,
                "description": description or title,
            }

            if validate_article(article):
                articles.append(article)

        logger.info(f"Successfully parsed {len(articles)} valid articles")
        return articles

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(articles, feed_name, feed_title, feed_description, feed_url):
    """Generate RSS feed from articles."""
    try:
        fg = FeedGenerator()
        fg.title(feed_title)
        fg.description(feed_description)
        fg.link(href=feed_url)
        fg.language("en")

        # Set feed metadata
        fg.author({"name": feed_title})
        fg.subtitle(feed_description)
        fg.link(href=feed_url, rel="alternate")
        fg.link(href=f"{feed_url}/feed_{feed_name}.xml", rel="self")

        # Add entries
        for article in articles:
            fe = fg.add_entry()
            fe.title(article["title"])
            fe.description(article["description"])
            fe.link(href=article["link"])
            fe.published(article["date"])
            fe.id(article["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def save_rss_feed(feed_generator, feed_name):
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


def main(source_url="https://www.lesechos.fr/travailler-mieux/", feed_name="lesechos_travailler_mieux"):
    """Main function to generate RSS feed."""
    try:
        # Fetch content
        html_content = fetch_content(source_url)

        # Parse articles from HTML
        articles = parse_html(html_content, source_url)

        # Generate RSS feed
        feed = generate_rss_feed(
            articles,
            feed_name=feed_name,
            feed_title="Les Échos - Travailler Mieux",
            feed_description="Actualités et conseils pour mieux travailler",
            feed_url=source_url,
        )

        # Save feed to file
        output_file = save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
