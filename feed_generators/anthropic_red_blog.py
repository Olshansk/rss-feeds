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


def fetch_red_content(url="https://red.anthropic.com/"):
    """Fetch content from Anthropic's red team blog."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching red team blog content: {str(e)}")
        raise


def parse_date(date_text):
    """Parse date text from article pages (e.g., 'November 12, 2025', 'September 29, 2025')."""
    date_formats = [
        "%B %d, %Y",  # November 12, 2025
        "%b %d, %Y",  # Nov 12, 2025
        "%B %Y",      # November 2025 (fallback)
        "%b %Y",      # Nov 2025 (fallback)
    ]

    for date_format in date_formats:
        try:
            date = datetime.strptime(date_text, date_format)
            return date.replace(tzinfo=pytz.UTC)
        except ValueError:
            continue

    logger.warning(f"Could not parse date: {date_text}")
    return None


def fetch_article_date(article_url):
    """Fetch the publication date from an individual article page."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(article_url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Look for date in d-article section
        article_section = soup.select_one("d-article")
        if article_section:
            # The date is typically in the first <p> tag
            first_p = article_section.select_one("p")
            if first_p:
                date_text = first_p.text.strip()
                date = parse_date(date_text)
                if date:
                    logger.debug(f"Found date '{date_text}' for {article_url}")
                    return date

        logger.warning(f"Could not find date in article: {article_url}")
        return None

    except Exception as e:
        logger.warning(f"Error fetching article date from {article_url}: {str(e)}")
        return None


def parse_red_html(html_content):
    """Parse the red team blog HTML content and extract article information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        articles = []
        seen_links = set()

        # Find the table of contents container
        toc = soup.select_one("div.toc")
        if not toc:
            logger.error("Could not find table of contents container")
            return articles

        current_date = None

        # Iterate through all children to process dates and articles in order
        for elem in toc.children:
            # Skip text nodes and non-tag elements
            if not hasattr(elem, 'name'):
                continue

            # Check if this is a date divider
            if elem.name == "div" and "date" in elem.get("class", []):
                date_text = elem.text.strip()
                current_date = parse_date(date_text)
                logger.debug(f"Found date section: {date_text}")
                continue

            # Check if this is an article link or a div containing an article link
            article_link = None
            if elem.name == "a" and "note" in elem.get("class", []):
                article_link = elem
            elif elem.name == "div":
                # Some articles are wrapped in divs (e.g., for scheduled releases)
                article_link = elem.select_one("a.note")

            if not article_link:
                continue

            # Extract article information
            href = article_link.get("href", "")
            if not href:
                continue

            # Build full URL
            if href.startswith("http"):
                link = href
            elif href.startswith("/"):
                link = f"https://red.anthropic.com{href}"
            else:
                link = f"https://red.anthropic.com/{href}"

            # Skip duplicates
            if link in seen_links:
                continue
            seen_links.add(link)

            # Extract title
            title_elem = article_link.select_one("h3")
            if not title_elem:
                logger.warning(f"Could not extract title for link: {link}")
                continue
            title = title_elem.text.strip()

            # Extract description
            description_elem = article_link.select_one("div.description")
            description = description_elem.text.strip() if description_elem else title

            # Fetch actual publication date from the article page
            article_date = fetch_article_date(link)

            # Fallback to current date from main page if fetching fails
            if not article_date:
                article_date = current_date if current_date else datetime.now(pytz.UTC)
                logger.warning(f"Using fallback date for article: {title}")

            # Create article object
            article = {
                "title": title,
                "link": link,
                "date": article_date,
                "description": description,
            }

            articles.append(article)
            logger.debug(f"Found article: {title} (date: {article_date})")

        logger.info(f"Successfully parsed {len(articles)} articles")
        return articles

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(articles, feed_name="anthropic_red"):
    """Generate RSS feed from red team blog articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic Frontier Red Team Blog")
        fg.description("Research from Anthropic's Frontier Red Team on what frontier AI models mean for national security")
        fg.link(href="https://red.anthropic.com/")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic Frontier Red Team"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Evidence-based analysis about AI's implications for cybersecurity, biosecurity, and autonomous systems")
        fg.link(href="https://red.anthropic.com/", rel="alternate")
        fg.link(href=f"https://anthropic.com/feed_{feed_name}.xml", rel="self")

        # Sort articles by date (newest first)
        sorted_articles = sorted(articles, key=lambda x: x["date"], reverse=True)

        # Add entries
        for article in sorted_articles:
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


def save_rss_feed(feed_generator, feed_name="anthropic_red"):
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


def main(feed_name="anthropic_red"):
    """Main function to generate RSS feed from Anthropic's red team blog."""
    try:
        # Fetch blog content
        html_content = fetch_red_content()

        # Parse articles from HTML
        articles = parse_red_html(html_content)

        if not articles:
            logger.warning("No articles found")
            return False

        # Generate RSS feed
        feed = generate_rss_feed(articles, feed_name)

        # Save feed to file
        output_file = save_rss_feed(feed, feed_name)

        logger.info(f"Successfully generated RSS feed with {len(articles)} articles")
        return True

    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False


if __name__ == "__main__":
    main()
