import logging
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import get_feeds_dir, setup_feed_links, sort_posts_for_feed

RSS_URL = "https://openai.com/news/rss.xml"
BLOG_URL = "https://openai.com/news/engineering/"
CATEGORY = "Engineering"
FEED_NAME = "openai_engineering"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def fetch_rss_content(url: str = RSS_URL) -> str:
    """Fetch the official OpenAI news RSS feed."""
    logger.info("Fetching RSS content from %s", url)
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.text


def parse_engineering_posts(rss_content: str) -> list[dict]:
    """Parse Engineering-tagged items from the official OpenAI RSS feed."""
    soup = BeautifulSoup(rss_content, "xml")
    posts = []

    for item in soup.find_all("item"):
        category = item.find("category")
        if not category or category.get_text(strip=True) != CATEGORY:
            continue

        title = item.find("title")
        link = item.find("link")
        description = item.find("description")
        pub_date = item.find("pubDate")

        if not title or not link:
            logger.warning("Skipping item missing title or link")
            continue

        parsed_date = None
        if pub_date and pub_date.get_text(strip=True):
            parsed_date = parsedate_to_datetime(pub_date.get_text(strip=True))

        posts.append(
            {
                "title": title.get_text(strip=True),
                "link": link.get_text(strip=True),
                "description": description.get_text(strip=True) if description else "",
                "date": parsed_date,
                "category": CATEGORY,
            }
        )

    logger.info("Parsed %s engineering posts", len(posts))
    return posts


def generate_rss_feed(posts: list[dict]) -> FeedGenerator:
    """Generate the RSS feed for OpenAI Engineering posts."""
    fg = FeedGenerator()
    fg.title("OpenAI Engineering")
    fg.description("Engineering posts from the official OpenAI news feed")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)
    fg.language("en")

    for post in sort_posts_for_feed(posts, date_field="date"):
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.link(href=post["link"])
        fe.description(post["description"])

        if post["date"] is not None:
            fe.published(post["date"])
            fe.updated(post["date"])

        fe.category(term=post["category"])

    return fg


def main() -> None:
    """Generate and save the OpenAI Engineering RSS feed."""
    rss_content = fetch_rss_content()
    posts = parse_engineering_posts(rss_content)

    if not posts:
        raise RuntimeError("No engineering posts found in the OpenAI RSS feed")

    output_file = get_feeds_dir() / f"feed_{FEED_NAME}.xml"
    generate_rss_feed(posts).rss_file(str(output_file), pretty=True)
    logger.info("Saved RSS feed to %s", output_file)


if __name__ == "__main__":
    main()
