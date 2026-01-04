import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

import pytz
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils import sort_posts_for_feed

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def stable_fallback_date(identifier):
    """Generate a stable date from a URL or title hash.

    This prevents RSS readers from seeing entries as 'new' when date
    extraction fails intermittently.
    """
    hash_val = abs(hash(identifier)) % 730  # ~2 years of days
    epoch = datetime(2023, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)
    return epoch + timedelta(days=hash_val)


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


def ensure_feeds_directory():
    """Ensure the feeds directory exists."""
    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    return feeds_dir


def setup_selenium_driver():
    """Set up Selenium WebDriver with undetected-chromedriver."""
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    return uc.Chrome(options=options)


def fetch_news_content(url="https://www.anthropic.com/news"):
    """Fetch the fully loaded HTML content of the news page using Selenium."""
    driver = None
    try:
        logger.info(f"Fetching content from URL: {url}")
        driver = setup_selenium_driver()
        driver.get(url)

        # Wait for initial page load
        wait_time = 5
        logger.info(f"Waiting {wait_time} seconds for the page to fully load...")
        time.sleep(wait_time)

        # Wait for news articles to be present
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/news/']"))
            )
            logger.info("News articles loaded successfully")
        except Exception:
            logger.warning("Could not confirm articles loaded, proceeding anyway...")

        # Click "See more" button repeatedly until it's no longer available
        max_clicks = 20  # Safety limit
        clicks = 0
        while clicks < max_clicks:
            try:
                # Look for the "See more" button using multiple selectors
                see_more_button = None
                selectors = [
                    "[class*='seeMore']",
                    "[class*='see-more']",
                    "button[class*='More']",
                ]
                for selector in selectors:
                    try:
                        see_more_button = driver.find_element(By.CSS_SELECTOR, selector)
                        if see_more_button and see_more_button.is_displayed():
                            break
                        see_more_button = None
                    except Exception:
                        continue

                # Also try finding by text content using XPath
                if not see_more_button:
                    try:
                        see_more_button = driver.find_element(
                            By.XPATH,
                            "//*[contains(text(), 'See more') or contains(text(), 'Load more')]",
                        )
                    except Exception:
                        pass

                if see_more_button and see_more_button.is_displayed():
                    logger.info(f"Clicking 'See more' button (click {clicks + 1})...")
                    driver.execute_script("arguments[0].click();", see_more_button)
                    clicks += 1
                    time.sleep(2)  # Wait for content to load
                else:
                    logger.info(
                        f"No more 'See more' button found after {clicks} clicks"
                    )
                    break
            except Exception as e:
                # No more "See more" button found
                logger.info(
                    f"No more 'See more' button found after {clicks} clicks: {e}"
                )
                break

        html_content = driver.page_source
        logger.info("Successfully fetched HTML content")
        return html_content

    except Exception as e:
        logger.error(f"Error fetching content: {e}")
        raise
    finally:
        if driver:
            driver.quit()


def extract_title(card):
    """Extract title using multiple fallback selectors."""
    selectors = [
        # New FeaturedGrid layout
        "h2[class*='featuredTitle']",
        "h4[class*='title']",
        # New PublicationList layout
        "span[class*='title']",
        # Legacy selectors
        "h3.PostCard_post-heading__Ob1pu",
        "h3.Card_headline__reaoT",
        "h3[class*='headline']",
        "h3[class*='heading']",
        "h2[class*='headline']",
        "h2[class*='heading']",
        "h3",
        "h2",
    ]
    for selector in selectors:
        elem = card.select_one(selector)
        if elem and elem.text.strip():
            return elem.text.strip()
    return None


def extract_date(card):
    """Extract date using multiple fallback selectors and formats."""
    selectors = [
        # New layout selectors - time element is most reliable
        "time[class*='date']",
        "time",
        # Legacy selectors
        "p.detail-m",
        "div.PostList_post-date__djrOA",
        "p[class*='date']",
        "div[class*='date']",
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
        # New layout selectors
        "span[class*='subject']",  # PublicationList layout
        "span.caption.bold",  # FeaturedGrid layout (category before date)
        # Legacy selectors
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
            if any(
                month in text
                for month in [
                    "Jan",
                    "Feb",
                    "Mar",
                    "Apr",
                    "May",
                    "Jun",
                    "Jul",
                    "Aug",
                    "Sep",
                    "Oct",
                    "Nov",
                    "Dec",
                ]
            ):
                continue
            return text

    return "News"


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
        unknown_structures = 0

        # Find all links that point to news articles
        # Use flexible selectors to catch current and future card types
        # Handle both relative (/news/...) and absolute (https://www.anthropic.com/news/...) URLs
        all_news_links = soup.select(
            'a[href*="/news/"], a[href*="anthropic.com/news/"]'
        )

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

            # Skip the main news page link and anchor links
            if link.endswith("/news") or link.endswith("/news/") or "/news#" in link:
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
                date = stable_fallback_date(link)

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
            logger.warning(
                f"Encountered {unknown_structures} links with unknown or invalid structures"
            )

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
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic News"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Latest updates from Anthropic's newsroom")
        # Set links - self link first, then alternate (which becomes the main <link>)
        fg.link(
            href=f"https://www.anthropic.com/feeds/feed_{feed_name}.xml", rel="self"
        )
        fg.link(href="https://www.anthropic.com/news", rel="alternate")

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
        # Fetch news content using Selenium
        html_content = fetch_news_content()

        # Parse articles from HTML
        articles = parse_news_html(html_content)

        if not articles:
            logger.warning("No articles found. Please check the HTML structure.")
            return False

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
