import logging
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

RSS_URL = "https://openai.com/news/rss.xml"
BLOG_URL = "https://openai.com/news/research/"
CATEGORY = "Research"
FEED_NAME = "openai_research"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_project_root():
    """Get the project root directory."""
    return Path(__file__).parent.parent


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


def parse_research_posts(rss_content: str) -> list[dict]:
    """Parse Research-tagged items from the official OpenAI RSS feed."""
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

    logger.info("Parsed %s research posts", len(posts))
    return posts


def generate_rss_feed(posts: list[dict]) -> FeedGenerator:
    """Generate the RSS feed for OpenAI Research posts."""
    fg = FeedGenerator()
    fg.title("OpenAI Research News")
    fg.description("Latest research news and updates from OpenAI")
    fg.link(href=BLOG_URL)
    fg.language("en")

    # Sort posts by date, newest first (handle None dates)
    sorted_posts = sorted(
        posts,
        key=lambda p: p["date"] if p["date"] else "1970-01-01",
        reverse=True
    )

    for post in sorted_posts:
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.link(href=post["link"])
        fe.description(post["description"])

        if post["date"] is not None:
            fe.published(post["date"])

        fe.category(term=post["category"])

    return fg


def main() -> None:
    """Generate and save the OpenAI Research RSS feed."""
    rss_content = fetch_rss_content()
    posts = parse_research_posts(rss_content)

    if not posts:
        logger.warning("No research posts found in the OpenAI RSS feed")
        # Still generate an empty feed (preserving structure)
        posts = []

    feeds_dir = get_project_root() / "feeds"
    feeds_dir.mkdir(exist_ok=True)
    output_file = feeds_dir / f"feed_{FEED_NAME}.xml"

    generate_rss_feed(posts).rss_file(str(output_file), pretty=True)
    logger.info("Saved RSS feed to %s", output_file)


if __name__ == "__main__":
    main()
