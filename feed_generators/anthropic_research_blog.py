import time
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from utils import (
    save_rss_feed,
    setup_feed_links,
    setup_logging,
    setup_selenium_driver,
    sort_posts_for_feed,
)

logger = setup_logging()

FEED_NAME = "anthropic_research"
BLOG_URL = "https://www.anthropic.com/research"


def fetch_research_content_selenium(url=BLOG_URL):
    """Fetch the fully loaded HTML content of the research page using Selenium."""
    driver = None
    try:
        logger.info(f"Fetching content from URL: {url}")
        driver = setup_selenium_driver()
        driver.get(url)

        # Wait for the page to fully load
        wait_time = 10
        logger.info(f"Waiting {wait_time} seconds for the page to fully load...")
        time.sleep(wait_time)

        # Wait for research articles to load by checking for specific elements
        try:
            # Wait for research articles to be present
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/research/']")))
            logger.info("Research articles loaded successfully")
        except Exception:
            logger.warning("Could not confirm articles loaded, proceeding anyway...")

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
        "h3",
        "h2",
        "h1",
        ".Card_headline__reaoT",
        "h3[class*='headline']",
        "h2[class*='headline']",
        "h3[class*='title']",
        "h2[class*='title']",
    ]

    for selector in selectors:
        elem = card.select_one(selector)
        if elem and elem.text.strip():
            title = elem.text.strip()
            # Clean up whitespace
            title = " ".join(title.split())
            if len(title) >= 5:
                return title

    # Try using link text as last resort
    if hasattr(card, 'text'):
        text = card.text.strip()
        text = " ".join(text.split())
        if len(text) >= 5:
            return text

    return None


def extract_date(card):
    """Extract date using multiple fallback selectors and formats."""
    selectors = [
        "p.detail-m",  # Current format on listing page
        ".detail-m",
        "time",
        "[class*='timestamp']",
        "[class*='date']",
        ".PostDetail_post-timestamp__TBJ0Z",
        ".text-label",
    ]

    date_formats = [
        "%b %d, %Y",
        "%B %d, %Y",
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%b %d %Y",
        "%B %d %Y",
    ]

    # Look for date in the card and its parents
    elements_to_check = [card]
    if hasattr(card, 'parent') and card.parent:
        elements_to_check.append(card.parent)
        if card.parent.parent:
            elements_to_check.append(card.parent.parent)

    for element in elements_to_check:
        for selector in selectors:
            date_elem = element.select_one(selector)
            if date_elem:
                date_text = date_elem.text.strip()
                for date_format in date_formats:
                    try:
                        date = datetime.strptime(date_text, date_format)
                        return date.replace(tzinfo=pytz.UTC)
                    except ValueError:
                        continue

    return None


def validate_article(article):
    """Validate that article has all required fields with reasonable values."""
    if not article.get("title") or len(article["title"]) < 5:
        return False
    if not article.get("link") or not article["link"].startswith("http"):
        return False
    # Date can be None for research articles
    return True


def parse_research_html(html_content):
    """Parse the research HTML content and extract article information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        articles = []
        seen_links = set()

        # Look for research article links using flexible selector
        research_links = soup.select("a[href*='/research/']")
        logger.info(f"Found {len(research_links)} potential research article links")

        for link in research_links:
            try:
                href = link.get("href", "")
                if not href:
                    continue

                # Skip the main research page
                if href == "/research" or href.endswith("/research/"):
                    continue

                # Construct full URL
                if href.startswith("https://"):
                    full_url = href
                elif href.startswith("/"):
                    full_url = "https://www.anthropic.com" + href
                else:
                    continue

                # Skip duplicates
                if full_url in seen_links:
                    continue
                seen_links.add(full_url)

                # Extract title
                title = extract_title(link)
                if not title:
                    logger.debug(f"Could not extract title for link: {full_url}")
                    continue

                # Extract date (can be None for research articles)
                date = extract_date(link)
                if date:
                    logger.info(f"Found article: {title} - {date}")
                else:
                    logger.info(f"Found article (no date): {title}")

                # Determine category from URL
                category = "Research"
                if "/news/" in href:
                    category = "News"

                article = {
                    "title": title,
                    "link": full_url,
                    "date": date,  # Can be None
                    "category": category,
                    "description": title,
                }

                # Validate article
                if validate_article(article):
                    articles.append(article)
                else:
                    logger.debug(f"Article failed validation: {full_url}")

            except Exception as e:
                logger.warning(f"Error parsing research link: {str(e)}")
                continue

        logger.info(f"Successfully parsed {len(articles)} unique research articles")
        return articles

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(articles):
    """Generate RSS feed from research articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic Research")
        fg.description("Latest research papers and updates from Anthropic")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic Research Team"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Latest research from Anthropic")
        setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

        # Sort articles for correct feed order (newest first in output)
        # Articles without dates will appear at the end
        articles_sorted = sort_posts_for_feed(articles, date_field="date")

        # Add entries
        for article in articles_sorted:
            fe = fg.add_entry()
            fe.title(article["title"])
            fe.description(article["description"])
            fe.link(href=article["link"])

            # Only set published date if we have a valid date
            if article["date"]:
                fe.published(article["date"])

            fe.category(term=article["category"])
            fe.id(article["link"])

        logger.info("Successfully generated RSS feed")
        return fg

    except Exception as e:
        logger.error(f"Error generating RSS feed: {str(e)}")
        raise


def main(full_reset=False):
    """Main function to generate RSS feed from Anthropic's research page."""
    try:
        # Fetch research content using Selenium
        html_content = fetch_research_content_selenium()

        # Parse articles from HTML
        articles = parse_research_html(html_content)

        if not articles:
            logger.warning("No articles found. Please check the HTML structure.")
            return False

        # Generate RSS feed
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
