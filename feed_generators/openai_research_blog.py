import requests
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import logging
from pathlib import Path
import re

# Debug flag for development
print_debug = True

# Set to 500 to ensure we get all articles (160 as of 01/2025)
LIMIT = 500

def print_debug(*args, **kwargs):
    if print_debug:
        print(*args, **kwargs)

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

def fetch_blog_content(url):
    """Fetch blog content from the given URL with robust headers."""
    try:
        print("Fetching content from URL:", url)
        # Create a session object to maintain cookies
        session = requests.Session()

        # Complete browser headers to avoid blocking
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1"
        }

        session.headers.update(headers)
        response = session.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"Error fetching blog content: {str(e)}")
        raise

def parse_date(date_str):
    """Parse date string to datetime object with support for multiple formats."""
    try:
        # Try different date formats
        formats = [
            "%b %d, %Y",  # Dec 9, 2024
            "%B %d, %Y",  # December 9, 2024
            "%Y-%m-%d",   # 2024-12-09
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=pytz.UTC)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None
    except Exception as e:
        logger.error(f"Error parsing date '{date_str}': {str(e)}")
        return None

def extract_metadata(element):
    """Extract metadata from a blog post element."""
    try:
        print_debug("Processing new article element:", element.get("href", "unknown"))
        # Title - look in multiple places with different classes
        title_elem = (
            element.select_one("div.line-clamp-2, div.line-clamp-4") or
            element.select_one("h2") or
            element.select_one("[class*='title']")
        )
        title = title_elem.get_text(strip=True) if title_elem else None
        print_debug("Found title:", title)

        # Date - check multiple locations and formats
        date_elem = (
            element.select_one("span.text-small") or
            element.select_one("[class*='date']") or
            element.find_parent("div", class_="gap-3xs").find("span", class_="text-small")
            if element.find_parent("div", class_="gap-3xs") else None
        )
        date_str = date_elem.get_text(strip=True) if date_elem else None
        pub_date = parse_date(date_str) if date_str else None
        print_debug("Found date string:", date_str)
        print_debug("Parsed date:", pub_date)

        # Description - multiple possible locations
        description_elem = (
            element.select_one("p") or
            element.select_one("[class*='description']") or
            element.select_one("div.line-clamp-2, div.line-clamp-4")
        )
        description = description_elem.get_text(strip=True) if description_elem else "OpenAI Research"

        # Link
        href = element.get("href", "")
        if href.startswith("/"):
            href = f"https://openai.com{href}"

        print_debug("Final metadata:", {
            "title": title,
            "date": pub_date,
            "description": description,
            "link": href
        })

        return {
            "title": title,
            "date": pub_date,
            "description": description,
            "link": href
        }
    except Exception as e:
        logger.error(f"Error extracting metadata: {str(e)}")
        return None

def parse_blog_html(html_content):
    """Parse the blog HTML content and extract post information."""
    try:
        print_debug("Starting HTML parsing")
        soup = BeautifulSoup(html_content, "html.parser")
        blog_posts = []

        # Find all possible article containers
        print(html_content)
        articles = soup.find_all("a", href=lambda x: x and x.startswith("https://openai.com/index/"))

        print_debug(f"Found {len(articles)} potential articles")

        for article in articles:
            try:
                metadata = extract_metadata(article)
                if metadata and metadata["title"] and metadata["date"]:
                    blog_posts.append(metadata)
                else:
                    logger.warning(f"Skipping article due to missing metadata: {article.get('href', 'unknown')}")
            except Exception as e:
                logger.warning(f"Error parsing article: {str(e)}")
                continue

        # Sort by date, newest first
        blog_posts.sort(key=lambda x: x["date"] or datetime.min.replace(tzinfo=pytz.UTC), reverse=True)

        logger.info(f"Successfully parsed {len(blog_posts)} blog posts")
        return blog_posts

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise

def generate_rss_feed(blog_posts, feed_name="openai_research"):
    """Generate RSS feed from blog posts."""
    try:
        fg = FeedGenerator()
        fg.title("OpenAI Research Blog")
        fg.description("Latest research updates from OpenAI")
        fg.link(href="https://openai.com/research")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "OpenAI"})
        fg.logo("https://openai.com/favicon.ico")
        fg.subtitle("Research publications and updates from OpenAI")
        fg.link(href=f"https://openai.com/research/?limit={LIMIT}", rel="alternate")
        fg.link(href=f"https://openai.com/feed_{feed_name}.xml", rel="self")

        # Add entries
        for post in blog_posts:
            fe = fg.add_entry()
            fe.title(post["title"])
            fe.description(post["description"])
            fe.link(href=post["link"])
            fe.published(post["date"])
            fe.id(post["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise

def save_rss_feed(feed_generator, feed_name="openai_research"):
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

def main(blog_url=f"https://openai.com/news/research?limit={LIMIT}", feed_name="openai_research"):
    """Main function to generate RSS feed from blog URL."""
    try:
        html_content = fetch_blog_content(blog_url)
        blog_posts = parse_blog_html(html_content)
        feed = generate_rss_feed(blog_posts, feed_name)
        output_file = save_rss_feed(feed, feed_name)
        return True
    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {str(e)}")
        return False

if __name__ == "__main__":
    main()