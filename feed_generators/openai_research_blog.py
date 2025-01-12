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

def setup_selenium_driver():
    """Set up Selenium WebDriver with undetected-chromedriver."""
    options = uc.ChromeOptions()
    options.add_argument("--headless")  # Ensure headless mode is enabled
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    return uc.Chrome(options=options)

def fetch_news_content_selenium(url):
    """Fetch the fully loaded HTML content of a webpage using Selenium."""
    driver = None
    try:
        logger.info(f"Fetching content from URL: {url}")
        driver = setup_selenium_driver()
        driver.get(url)

        # Log wait time
        wait_time = 5
        logger.info(f"Waiting {wait_time} seconds for the page to fully load...")
        time.sleep(wait_time)

        html_content = driver.page_source
        logger.info("Successfully fetched HTML content")
        return html_content

    except Exception as e:
        logger.error(f"Error fetching content: {e}")
        raise
    finally:
        if driver:
            driver.quit()

def parse_openai_news_html(html_content):
    """Parse the HTML content from OpenAI's Research News page."""
    soup = BeautifulSoup(html_content, "html.parser")
    articles = []

    # Extract news items that contain `/index` in the href
    news_items = soup.select("a[href*='/index']")  # Look for links containing '/index'

    for item in news_items:
        try:
            # Extract title
            title_elem = item.select_one("div.line-clamp-4")
            if not title_elem:
                continue
            title = title_elem.text.strip()

            # Extract link
            link = "https://openai.com" + item["href"]

            # Extract date
            date_elem = item.select_one("span.text-small")
            if date_elem:
                try:
                    date = datetime.strptime(date_elem.text.strip(), "%b %d, %Y")
                    date = date.replace(tzinfo=pytz.UTC)
                except Exception:
                    logger.warning(f"Date parsing failed for article: {title}")
                    date = datetime.now(pytz.UTC)
            else:
                date = datetime.now(pytz.UTC)

            articles.append(
                {"title": title, "link": link, "date": date, "category": "Research", "description": title}
            )
        except Exception as e:
            logger.warning(f"Skipping an article due to parsing error: {e}")
            continue

    logger.info(f"Parsed {len(articles)} articles")
    return articles

def generate_rss_feed(articles, feed_name="openai_research"):
    """Generate RSS feed from parsed articles."""
    fg = FeedGenerator()
    fg.title("OpenAI Research News")
    fg.description("Latest research news and updates from OpenAI")
    fg.link(href="https://openai.com/news/research")
    fg.language("en")

    for article in articles:
        fe = fg.add_entry()
        fe.title(article["title"])
        fe.link(href=article["link"])
        fe.description(article["description"])
        fe.published(article["date"])
        fe.category(term=article["category"])

    logger.info("RSS feed generated successfully")
    return fg

def save_rss_feed(feed_generator, feed_name="openai_research"):
    """Save RSS feed to an XML file."""
    feeds_dir = Path("feeds")
    feeds_dir.mkdir(exist_ok=True)
    output_file = feeds_dir / f"feed_{feed_name}.xml"
    feed_generator.rss_file(str(output_file), pretty=True)
    logger.info(f"RSS feed saved to {output_file}")
    return output_file

def main():
    """Main function to generate OpenAI Research News RSS feed."""
    url = "https://openai.com/news/research/?limit=500"

    try:
        html_content = fetch_news_content_selenium(url)
        articles = parse_openai_news_html(html_content)
        if not articles:
            logger.warning("No articles were parsed. Check your selectors.")
        feed = generate_rss_feed(articles)
        save_rss_feed(feed)
    except Exception as e:
        logger.error(f"Failed to generate RSS feed: {e}")

if __name__ == "__main__":
    main()