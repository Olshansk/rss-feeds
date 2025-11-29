import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path
import json
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


def extract_title(card):
    """Extract title using multiple fallback selectors."""
    selectors = [
        "h3.PostCard_post-heading__Ob1pu",
        "h3.Card_headline__reaoT",
        "h3[class*='headline']",
        "h3[class*='heading']",
        "h2[class*='headline']",
        "h2[class*='heading']",
        "h3",
        "h2",
        "span[class*='title']",
    ]
    for selector in selectors:
        elem = card.select_one(selector)
        if elem and elem.text.strip():
            return elem.text.strip()
    return None


def extract_date(card):
    """Extract date using multiple fallback selectors and formats."""
    selectors = [
        "p.detail-m",  # Current format on listing page
        "div.PostList_post-date__djrOA",
        "p[class*='date']",
        "div[class*='date']",
        "time",
    ]

    date_formats = [
        "%b %d, %Y",
        "%B %d, %Y",
        "%b %d %Y",
        "%B %d %Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
    ]

    for selector in selectors:
        # Use select() to get all matching elements, not just the first one
        elems = card.select(selector)
        for elem in elems:
            date_text = elem.text.strip()
            # Try to parse it as a date
            for date_format in date_formats:
                try:
                    date = datetime.strptime(date_text, date_format)
                    return date.replace(tzinfo=pytz.UTC)
                except ValueError:
                    continue

    return None


def extract_category(card, date_elem_text=None):
    """Extract category using multiple fallback selectors."""
    selectors = [
        "span.text-label",
        "p.detail-m",
        "span[class*='category']",
        "div[class*='category']",
    ]

    for selector in selectors:
        elem = card.select_one(selector)
        if elem:
            text = elem.text.strip()
            # Skip if this is the date element
            if date_elem_text and text == date_elem_text:
                continue
            # Skip if it looks like a date
            if any(month in text for month in ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                                 "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]):
                continue
            return text

    return "News"


def extract_articles_from_json(data, articles, seen_links):
    """Recursively extract articles from JSON data."""
    if isinstance(data, dict):
        if data.get("_type") == "post":
            title = data.get("title")
            slug = data.get("slug", {}).get("current")
            
            if title and slug:
                # Determine URL
                directories = data.get("directories", [])
                is_news = any(d.get("value") == "news" for d in directories)
                is_research = any(d.get("value") == "research" for d in directories)
                
                if is_news:
                    link = f"https://www.anthropic.com/news/{slug}"
                elif is_research:
                    link = f"https://www.anthropic.com/research/{slug}"
                else:
                    link = f"https://www.anthropic.com/news/{slug}"
                
                if link in seen_links:
                    return

                # Parse date
                date_str = data.get("publishedOn")
                if date_str:
                    try:
                        date_str = date_str.replace("Z", "+00:00")
                        date = datetime.fromisoformat(date_str)
                    except ValueError:
                        date = datetime.now(pytz.UTC)
                else:
                    date = datetime.now(pytz.UTC)

                # Category
                subjects = data.get("subjects", [])
                if subjects:
                    category = subjects[0].get("label", "News")
                else:
                    category = "News"

                article = {
                    "title": title,
                    "link": link,
                    "date": date,
                    "category": category,
                    "description": data.get("summary") or title,
                }
                
                if validate_article(article):
                    articles.append(article)
                    seen_links.add(link)
            return

        for key, value in data.items():
            extract_articles_from_json(value, articles, seen_links)
            
    elif isinstance(data, list):
        for item in data:
            extract_articles_from_json(item, articles, seen_links)


def validate_article(article):
    """Validate that article has all required fields with reasonable values."""
    if not article.get("title") or len(article["title"]) < 5:
        logger.warning(f"Invalid title for article: {article.get('link', 'unknown')}")
        return False

    if not article.get("link") or not article["link"].startswith("http"):
        logger.warning(f"Invalid link for article: {article.get('title', 'unknown')}")
        return False

    if not article.get("date"):
        logger.warning(f"Missing date for article: {article.get('title', 'unknown')}")
        return False

    return True


def parse_news_html(html_content):
    """Parse the news HTML content and extract article information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        articles = []
        seen_links = set()
        
        # Strategy 1: Try to extract from Next.js JSON data (script tags)
        scripts = soup.find_all("script")
        json_found = False
        
        for script in scripts:
            if script.string and 'self.__next_f.push' in script.string:
                # Look for strings that look like JSON data chunks
                # The pattern is self.__next_f.push([1, "ID:JSON_STRING"])
                # We use a regex that handles escaped quotes inside the string
                matches = re.findall(r'self\.__next_f\.push\(\[1,\s*"((?:[^"\\]|\\.)*)"\]\)', script.string)
                for content_str in matches:
                    # The string starts with "ID:", e.g. "21:"
                    if ':' in content_str:
                        try:
                            # Unescape the string to get the inner JSON
                            # We wrap it in quotes to make it a valid JSON string for unescaping
                            unescaped_content = json.loads(f'"{content_str}"')
                            
                            # Remove the ID prefix (e.g. "21:")
                            if ':' in unescaped_content:
                                _, json_payload = unescaped_content.split(':', 1)
                                
                                # Parse the actual data
                                data = json.loads(json_payload)
                                
                                # Extract articles recursively
                                prev_count = len(articles)
                                extract_articles_from_json(data, articles, seen_links)
                                if len(articles) > prev_count:
                                    json_found = True
                                    
                        except Exception as e:
                            # It's expected that some chunks won't be valid JSON or won't contain articles
                            continue

        if json_found and len(articles) > 0:
            logger.info(f"Successfully parsed {len(articles)} articles from JSON data")
            return articles

        # Strategy 2: Fallback to HTML parsing
        logger.info("JSON parsing yielded no results, falling back to HTML parsing")
        unknown_structures = 0

        # Find all links that point to news articles
        # Use flexible selectors to catch current and future card types
        all_news_links = soup.select('a[href*="/news/"]')

        logger.info(f"Found {len(all_news_links)} potential news article links")

        for card in all_news_links:
            href = card.get("href", "")
            if not href:
                continue

            # Build full URL
            link = "https://www.anthropic.com" + href if href.startswith("/") else href

            # Skip duplicates
            if link in seen_links:
                continue

            # Skip the main news page link
            if link.endswith("/news") or link.endswith("/news/"):
                continue

            seen_links.add(link)

            # Extract title using fallback chain
            title = extract_title(card)
            if not title:
                logger.debug(f"Could not extract title for link: {link}")
                logger.debug(f"Card HTML preview: {str(card)[:200]}")
                unknown_structures += 1
                continue

            # Extract date using fallback chain
            date = extract_date(card)
            if not date:
                logger.warning(f"Could not extract date for article: {title}")
                date = datetime.now(pytz.UTC)

            # Extract category
            category = extract_category(card)

            # Create article object
            article = {
                "title": title,
                "link": link,
                "date": date,
                "category": category,
                "description": title,  # Using title as description fallback
            }

            # Validate article before adding
            if validate_article(article):
                articles.append(article)
            else:
                unknown_structures += 1

        if unknown_structures > 0:
            logger.warning(f"Encountered {unknown_structures} links with unknown or invalid structures")

        logger.info(f"Successfully parsed {len(articles)} valid articles")
        return articles

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(articles, feed_name="anthropic_news"):
    """Generate RSS feed from news articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic News")
        fg.description("Latest news and updates from Anthropic")
        fg.link(href="https://www.anthropic.com/news")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic News"})
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


def save_rss_feed(feed_generator, feed_name="anthropic_news"):
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


def main(feed_name="anthropic_news"):
    """Main function to generate RSS feed from Anthropic's news page."""
    try:
        # Fetch news content
        html_content = fetch_news_content()

        # Parse articles from HTML
        articles = parse_news_html(html_content)

        # Generate RSS feed with all articles
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
