import requests
import xml.etree.ElementTree as ET
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
    """Fetch content from URL with proper headers."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching content from {url}: {str(e)}")
        raise


def parse_engineering_articles(html_content):
    """Parse engineering articles from HTML content."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        articles = []

        # Find all article containers
        article_containers = soup.select("article.ArticleList_article__LIMds")

        for container in article_containers:
            try:
                # Extract link
                link_elem = container.select_one("a.ArticleList_cardLink__VWIzl")
                if not link_elem or not link_elem.get("href"):
                    continue
                
                link = link_elem["href"]
                if link.startswith("/"):
                    link = "https://www.anthropic.com" + link

                # Extract title - try h2 first, then h3
                title_elem = container.select_one("h2") or container.select_one("h3")
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)

                # Extract date
                date_elem = container.select_one("div.ArticleList_date__2VTRg")
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    try:
                        # Parse date format like "Apr 18, 2025" or "Dec 19, 2024"
                        date = datetime.strptime(date_text, "%b %d, %Y")
                        date = date.replace(tzinfo=pytz.UTC)
                    except ValueError:
                        logger.warning(f"Could not parse date '{date_text}' for article: {title}")
                        date = datetime.now(pytz.UTC)
                else:
                    # No date found, use current date
                    date = datetime.now(pytz.UTC)

                # Extract summary/description
                summary_elem = container.select_one("p.ArticleList_summary__G96cV")
                description = summary_elem.get_text(strip=True) if summary_elem else title

                # Check if featured
                featured_elem = container.select_one("span.ArticleList_featuredLabel__cqbtx")
                is_featured = featured_elem is not None

                # Set category
                category = "Engineering"
                if is_featured:
                    category = "Engineering - Featured"

                article = {
                    "title": title,
                    "link": link,
                    "date": date,
                    "category": category,
                    "description": description
                }

                articles.append(article)

            except Exception as e:
                logger.error(f"Error parsing individual engineering article: {str(e)}")
                continue

        logger.info(f"Successfully parsed {len(articles)} engineering articles")
        return articles

    except Exception as e:
        logger.error(f"Error parsing engineering HTML content: {str(e)}")
        raise


def parse_news_articles(html_content):
    """Parse news articles from HTML content."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        articles = []

        # Find all article cards
        news_cards = soup.select("a.PostCard_post-card__z_Sqq")

        for card in news_cards:
            try:
                # Extract title
                title_elem = card.select_one("h3.PostCard_post-heading__Ob1pu")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)

                # Extract link
                link = "https://www.anthropic.com" + card["href"] if card["href"].startswith("/") else card["href"]

                # Extract date
                date_elem = card.select_one("div.PostList_post-date__djrOA")
                if date_elem:
                    try:
                        date = datetime.strptime(date_elem.get_text(strip=True), "%b %d, %Y")
                        date = date.replace(tzinfo=pytz.UTC)
                    except ValueError:
                        logger.warning(f"Could not parse date for article: {title}")
                        date = datetime.now(pytz.UTC)
                else:
                    date = datetime.now(pytz.UTC)

                # Extract category
                category_elem = card.select_one("span.text-label")
                category = category_elem.get_text(strip=True) if category_elem else "News"

                # Description is title for news articles
                description = title

                article = {
                    "title": title,
                    "link": link,
                    "date": date,
                    "category": category,
                    "description": description
                }

                articles.append(article)

            except Exception as e:
                logger.error(f"Error parsing individual news article: {str(e)}")
                continue

        logger.info(f"Successfully parsed {len(articles)} news articles")
        return articles

    except Exception as e:
        logger.error(f"Error parsing news HTML content: {str(e)}")
        raise


def fetch_all_anthropic_content():
    """Fetch and parse content from both news and engineering pages."""
    all_articles = []
    
    # Fetch news articles
    try:
        logger.info("Fetching news content...")
        news_html = fetch_content("https://www.anthropic.com/news")
        news_articles = parse_news_articles(news_html)
        all_articles.extend(news_articles)
    except Exception as e:
        logger.error(f"Failed to fetch news content: {str(e)}")
        # Continue with engineering even if news fails
    
    # Fetch engineering articles
    try:
        logger.info("Fetching engineering content...")
        eng_html = fetch_content("https://www.anthropic.com/engineering")
        eng_articles = parse_engineering_articles(eng_html)
        all_articles.extend(eng_articles)
    except Exception as e:
        logger.error(f"Failed to fetch engineering content: {str(e)}")
        # Continue even if engineering fails
    
    if not all_articles:
        raise Exception("Failed to fetch any articles from both sources")
    
    # Sort by date (newest first)
    all_articles.sort(key=lambda x: x['date'], reverse=True)
    
    logger.info(f"Successfully fetched {len(all_articles)} total articles")
    return all_articles


def generate_rss_feed(articles, feed_name="anthropic"):
    """Generate RSS feed from articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic News & Engineering")
        fg.description("Latest news and engineering updates from Anthropic")
        fg.link(href="https://www.anthropic.com")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Latest updates from Anthropic's newsroom and engineering blog")
        fg.link(href="https://www.anthropic.com", rel="alternate")
        fg.link(href=f"https://anthropic.com/feeds/feed_{feed_name}.xml", rel="self")

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


def get_existing_links_from_feed(feed_path):
    """Parse the existing RSS feed and return a set of all article links."""
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


def main(feed_name="anthropic"):
    """Main function to generate RSS feed from Anthropic's news and engineering pages."""
    try:
        # Fetch all content
        articles = fetch_all_anthropic_content()

        # Deduplicate using existing feed
        feeds_dir = ensure_feeds_directory()
        feed_path = feeds_dir / f"feed_{feed_name}.xml"
        existing_links = get_existing_links_from_feed(feed_path)
        new_articles = [a for a in articles if a["link"] not in existing_links]

        if not new_articles:
            logger.info("No new articles to add. Skipping feed update.")
            return True

        logger.info(f"Found {len(new_articles)} new articles out of {len(articles)} total")

        # Generate RSS feed with ALL articles (not just new ones)
        # This ensures the feed contains the complete set of articles
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
