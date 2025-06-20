import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from datetime import datetime
import pytz
from feedgen.feed import FeedGenerator
import time
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


def setup_selenium_driver():
    """Set up Selenium WebDriver with undetected-chromedriver."""
    options = uc.ChromeOptions()
    options.add_argument("--headless")  # Ensure headless mode is enabled
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )
    return uc.Chrome(options=options)


def fetch_research_content_selenium(url="https://www.anthropic.com/research"):
    """Fetch the fully loaded HTML content of the research page using Selenium."""
    driver = None
    try:
        logger.info(f"Fetching content from URL: {url}")
        driver = setup_selenium_driver()
        driver.get(url)

        # Wait for the page to fully load
        wait_time = 8
        logger.info(f"Waiting {wait_time} seconds for the page to fully load...")
        time.sleep(wait_time)

        # Wait for research articles to load by checking for specific elements
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            # Wait for research articles to be present
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/research/'], a[href*='/news/']"))
            )
            logger.info("Research articles loaded successfully")
        except:
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


def parse_research_html(html_content):
    """Parse the research HTML content and extract article information."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        articles = []

        # Look for research and news articles with various selectors
        selectors = [
            "a[href*='/research/']",  # Research articles
            "a[href*='/news/']",  # News articles
            "a.PostCard_post-card__z_Sqq",  # Post cards (if present)
        ]

        found_links = set()  # To avoid duplicates

        for selector in selectors:
            links = soup.select(selector)
            logger.info(f"Found {len(links)} links with selector: {selector}")

            for link in links:
                try:
                    href = link.get("href", "")
                    if not href or href in found_links:
                        continue

                    found_links.add(href)

                    # Extract title - try multiple possible selectors
                    title = None
                    title_selectors = [
                        "h3",
                        "h2",
                        ".PostCard_post-heading__Ob1pu",
                        "[class*='heading']",
                        "[class*='title']",
                    ]

                    for title_sel in title_selectors:
                        title_elem = link.select_one(title_sel)
                        if title_elem and title_elem.text.strip():
                            title = title_elem.text.strip()
                            break

                    # If no title found in the link, try parent elements
                    if not title:
                        parent = link.parent
                        for _ in range(3):  # Check up to 3 parent levels
                            if parent:
                                for title_sel in title_selectors:
                                    title_elem = parent.select_one(title_sel)
                                    if title_elem and title_elem.text.strip():
                                        title = title_elem.text.strip()
                                        break
                                if title:
                                    break
                                parent = parent.parent

                    if not title:
                        # Use the link text itself as fallback
                        title = link.text.strip()
                        if len(title) < 10:  # Skip very short titles
                            continue

                    # Clean up title
                    title = " ".join(title.split())  # Remove extra whitespace

                    # Construct full URL
                    if href.startswith("https://"):
                        full_url = href
                    elif href.startswith("/"):
                        full_url = "https://www.anthropic.com" + href
                    else:
                        continue

                    # Extract date - try multiple selectors
                    date = None
                    date_selectors = [".PostList_post-date__djrOA", "[class*='date']", "[class*='timestamp']", "time"]

                    for date_sel in date_selectors:
                        date_elem = link.select_one(date_sel) or (link.parent and link.parent.select_one(date_sel))
                        if date_elem:
                            try:
                                date_str = date_elem.text.strip()
                                # Try different date formats
                                for date_format in ["%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"]:
                                    try:
                                        date = datetime.strptime(date_str, date_format)
                                        date = date.replace(tzinfo=pytz.UTC)
                                        break
                                    except ValueError:
                                        continue
                                if date:
                                    break
                            except:
                                continue

                    if not date:
                        date = datetime.now(pytz.UTC)

                    # Extract category
                    category = "Research"
                    category_elem = link.select_one("[class*='category']") or link.select_one(".text-label")
                    if category_elem:
                        category = category_elem.text.strip()

                    # Determine category from URL if not found
                    if "/research/" in href:
                        category = "Research"
                    elif "/news/" in href:
                        category = "News"

                    articles.append(
                        {
                            "title": title,
                            "link": full_url,
                            "date": date,
                            "category": category,
                            "description": title,  # Use title as description
                        }
                    )

                except Exception as e:
                    logger.warning(f"Skipping article due to parsing error: {str(e)}")
                    continue

        # Remove duplicates based on link
        seen_links = set()
        unique_articles = []
        for article in articles:
            if article["link"] not in seen_links:
                seen_links.add(article["link"])
                unique_articles.append(article)

        logger.info(f"Successfully parsed {len(unique_articles)} unique research articles")
        return unique_articles

    except Exception as e:
        logger.error(f"Error parsing HTML content: {str(e)}")
        raise


def generate_rss_feed(articles, feed_name="anthropic_research"):
    """Generate RSS feed from research articles."""
    try:
        fg = FeedGenerator()
        fg.title("Anthropic Research")
        fg.description("Latest research papers and updates from Anthropic")
        fg.link(href="https://www.anthropic.com/research")
        fg.language("en")

        # Set feed metadata
        fg.author({"name": "Anthropic Research Team"})
        fg.logo("https://www.anthropic.com/images/icons/apple-touch-icon.png")
        fg.subtitle("Latest research from Anthropic")
        fg.link(href="https://www.anthropic.com/research", rel="alternate")
        fg.link(href=f"https://anthropic.com/research/feed_{feed_name}.xml", rel="self")

        # Sort articles by date (most recent first)
        articles_sorted = sorted(articles, key=lambda x: x["date"], reverse=True)

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


def save_rss_feed(feed_generator, feed_name="anthropic_research"):
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


def main(feed_name="anthropic_research"):
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
