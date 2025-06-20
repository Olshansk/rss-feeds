import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path
import json
import os

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


def get_article_cache_file():
    """Get the path to the article cache file."""
    feeds_dir = ensure_feeds_directory()
    return feeds_dir / "anthropic_engineering_article_cache.json"


def load_article_cache():
    """Load the article cache from disk."""
    cache_file = get_article_cache_file()
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                cache = json.load(f)
                # Convert date strings back to datetime objects
                for link, data in cache.items():
                    data["date"] = datetime.fromisoformat(data["date"])
                return cache
        except Exception as e:
            logger.warning(f"Failed to load article cache: {e}")
    return {}


def save_article_cache(cache):
    """Save the article cache to disk."""
    cache_file = get_article_cache_file()
    try:
        # Convert datetime objects to strings for JSON serialization
        cache_to_save = {}
        for link, data in cache.items():
            cache_to_save[link] = {"title": data["title"], "date": data["date"].isoformat()}

        with open(cache_file, "w") as f:
            json.dump(cache_to_save, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save article cache: {e}")


def fetch_engineering_content(url="https://www.anthropic.com/engineering"):
    """Fetch engineering page content from Anthropic's website."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching engineering content: {str(e)}")
        raise


def parse_engineering_html(html_content):
    """Parse the engineering HTML content and extract article information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        articles = []

        # Load existing article cache
        article_cache = load_article_cache()
        current_time = datetime.now(pytz.UTC)
        cache_updated = False

        # Find the featured article first
        featured_article = soup.select_one("article.ArticleList_featured__2WCTd")
        if featured_article:
            # Extract title from featured article
            title_elem = featured_article.select_one("h2")
            if title_elem:
                title = title_elem.text.strip()

                # Extract link
                link_elem = featured_article.select_one("a.ArticleList_cardLink__VWIzl")
                if link_elem and link_elem.get("href"):
                    link = "https://www.anthropic.com" + link_elem["href"]

                    # Extract description
                    desc_elem = featured_article.select_one("p.ArticleList_summary__G96cV")
                    description = desc_elem.text.strip() if desc_elem else title

                    # Check if we have a cached date for this article
                    if link in article_cache:
                        date = article_cache[link]["date"]
                        logger.info(f"Using cached date for featured article: {title}")
                    else:
                        # Look for date in the featured article
                        date_elem = featured_article.select_one("div.ArticleList_date__2VTRg")
                        if date_elem:
                            try:
                                date_text = date_elem.text.strip()
                                date = datetime.strptime(date_text, "%b %d, %Y")
                                date = date.replace(hour=0, minute=0, second=0, tzinfo=pytz.UTC)
                            except ValueError:
                                logger.warning(f"Could not parse date '{date_text}' for featured article: {title}")
                                # Use current time as the "first seen" date
                                date = current_time
                        else:
                            # Use current time as the "first seen" date
                            logger.info(
                                f"No date found for featured article: {title}, using current time as first seen date"
                            )
                            date = current_time

                        # Cache this article
                        article_cache[link] = {"title": title, "date": date}
                        cache_updated = True

                    articles.append(
                        {
                            "title": title,
                            "link": link,
                            "description": description,
                            "date": date,
                            "category": "Engineering",
                        }
                    )
                    logger.info(f"Found featured article: {title}")

        # Find all other article cards
        article_cards = soup.select("article.ArticleList_article__LIMds:not(.ArticleList_featured__2WCTd)")

        for card in article_cards:
            try:
                # Extract title
                title_elem = card.select_one("h3")
                if not title_elem:
                    continue
                title = title_elem.text.strip()

                # Extract link
                link_elem = card.select_one("a.ArticleList_cardLink__VWIzl")
                if not link_elem or not link_elem.get("href"):
                    continue
                link = "https://www.anthropic.com" + link_elem["href"]

                # Check if we have a cached date for this article
                if link in article_cache:
                    date = article_cache[link]["date"]
                    logger.info(f"Using cached date for article: {title}")
                else:
                    # Extract date
                    date_elem = card.select_one("div.ArticleList_date__2VTRg")
                    if date_elem:
                        try:
                            date_text = date_elem.text.strip()
                            # Parse date format like "Apr 18, 2025"
                            date = datetime.strptime(date_text, "%b %d, %Y")
                            date = date.replace(hour=0, minute=0, second=0, tzinfo=pytz.UTC)
                        except ValueError:
                            logger.warning(f"Could not parse date '{date_text}' for article: {title}")
                            # Use current time as the "first seen" date
                            date = current_time
                    else:
                        # Use current time as the "first seen" date
                        logger.info(f"No date found for article: {title}, using current time as first seen date")
                        date = current_time

                    # Cache this article
                    article_cache[link] = {"title": title, "date": date}
                    cache_updated = True

                # Use title as description since there's no separate description for non-featured articles
                description = title

                articles.append(
                    {"title": title, "link": link, "description": description, "date": date, "category": "Engineering"}
                )
                logger.info(f"Found article: {title}")

            except Exception as e:
                logger.warning(f"Error parsing article card: {str(e)}")
                continue

        # Save the updated cache if needed
        if cache_updated:
            save_article_cache(article_cache)
            logger.info("Updated article cache with new articles")

        logger.info(f"Successfully parsed {len(articles)} articles")
        return articles

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(articles, feed_name="anthropic_engineering"):
    """Generate RSS feed from engineering articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic Engineering Blog")
        fg.description("Latest engineering articles and insights from Anthropic's engineering team")
        fg.link(href="https://www.anthropic.com/engineering")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic Engineering Team"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Inside the team building reliable AI systems")
        fg.link(href="https://www.anthropic.com/engineering", rel="alternate")
        fg.link(href=f"https://anthropic.com/engineering/feed_{feed_name}.xml", rel="self")

        # Sort articles by date (newest first)
        articles.sort(key=lambda x: x["date"], reverse=True)

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


def save_rss_feed(feed_generator, feed_name="anthropic_engineering"):
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


def main(feed_name="anthropic_engineering"):
    """Main function to generate RSS feed from Anthropic's engineering page."""
    try:
        # Fetch engineering content
        html_content = fetch_engineering_content()

        # Parse articles from HTML
        articles = parse_engineering_html(html_content)

        if not articles:
            logger.warning("No articles found on the engineering page")
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
