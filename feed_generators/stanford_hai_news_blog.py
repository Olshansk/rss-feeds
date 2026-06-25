"""Generate RSS feed for Stanford HAI News (https://hai.stanford.edu/news)."""

import argparse
import re
from datetime import datetime

import pytz
from bs4 import BeautifulSoup
from feedgen.feed import FeedGenerator

from utils import fetch_page, save_rss_feed, setup_feed_links, setup_logging, sort_posts_for_feed, stable_fallback_date

logger = setup_logging()

FEED_NAME = "stanford_hai_news"
BLOG_URL = "https://hai.stanford.edu/news"
BASE_URL = "https://hai.stanford.edu"

DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
)


def parse_date(date_text: str) -> datetime | None:
    """Parse date strings like 'May 27, 2026' into UTC datetimes."""
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(date_text.strip(), fmt).replace(tzinfo=pytz.UTC)
        except ValueError:
            continue
    return None


def extract_article_date(article_url: str) -> datetime:
    """Fetch an article page and extract its publish date."""
    try:
        article_html = fetch_page(article_url)
        soup = BeautifulSoup(article_html, "html.parser")

        # Common detail-page pattern: "Date June 01, 2026"
        for row in soup.select('[class*="DetailMeta_row"]'):
            text = row.get_text(" ", strip=True)
            match = DATE_RE.search(text)
            if match:
                parsed = parse_date(match.group(0))
                if parsed:
                    return parsed

        # Featured story pattern where date is shown directly
        for elem in soup.select('[class*="FeatureArticleMeta_date"]'):
            text = elem.get_text(" ", strip=True)
            parsed = parse_date(text)
            if parsed:
                return parsed

        # Fallback: any standalone month day, year text
        for elem in soup.find_all(["div", "span", "p"]):
            text = elem.get_text(" ", strip=True)
            match = DATE_RE.search(text)
            if match:
                parsed = parse_date(match.group(0))
                if parsed:
                    return parsed

        logger.warning(f"Could not parse publish date for {article_url}")
    except Exception as e:
        logger.warning(f"Failed to fetch article metadata for {article_url}: {e}")

    return stable_fallback_date(article_url)


def parse_news_listing(html_content: str) -> list[dict]:
    """Parse the HAI News listing page and extract article cards."""
    soup = BeautifulSoup(html_content, "html.parser")
    cards = soup.select('div[class*="ContentCard_root__"]')
    logger.info(f"Found {len(cards)} content cards")

    posts = []
    seen_links = set()

    for card in cards:
        try:
            link_elem = card.select_one('a[href*="/news/"]')
            title_elem = card.select_one("h2, h3, h4")
            desc_elem = card.select_one("p")

            if not link_elem or not title_elem:
                continue

            href = link_elem.get("href", "").strip()
            if not href or href in ("/news", "/news/"):
                continue

            link = f"{BASE_URL}{href}" if href.startswith("/") else href
            if link in seen_links:
                continue
            seen_links.add(link)

            title = title_elem.get_text(" ", strip=True)
            if not title:
                continue

            description = desc_elem.get_text(" ", strip=True) if desc_elem else title
            date = extract_article_date(link)

            posts.append(
                {
                    "title": title,
                    "link": link,
                    "description": description,
                    "date": date,
                    "category": "News",
                }
            )
        except Exception as e:
            logger.warning(f"Skipping malformed content card: {e}")

    logger.info(f"Parsed {len(posts)} HAI news posts")
    return posts


def generate_rss_feed(posts: list[dict]) -> FeedGenerator:
    fg = FeedGenerator()
    fg.title("Stanford HAI News")
    fg.description("Latest news and research updates from Stanford HAI")
    fg.language("en")
    fg.author({"name": "Stanford HAI"})
    fg.subtitle("Stanford Institute for Human-Centered Artificial Intelligence news")
    setup_feed_links(fg, blog_url=BLOG_URL, feed_name=FEED_NAME)

    for post in sort_posts_for_feed(posts, date_field="date"):
        fe = fg.add_entry()
        fe.title(post["title"])
        fe.description(post["description"])
        fe.link(href=post["link"])
        fe.id(post["link"])
        fe.category(term=post["category"])
        fe.published(post["date"])

    logger.info(f"Generated RSS feed with {len(posts)} entries")
    return fg


def main() -> bool:
    logger.info(f"Fetching {BLOG_URL}")
    html = fetch_page(BLOG_URL)
    posts = parse_news_listing(html)

    if not posts:
        logger.warning("No HAI news posts found. Check selectors.")
        return False

    feed = generate_rss_feed(posts)
    save_rss_feed(feed, FEED_NAME)
    logger.info("Done!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Stanford HAI News RSS feed")
    # --full is accepted for orchestrator compatibility even though this generator has no cache.
    parser.add_argument("--full", action="store_true", help="No-op (Stanford HAI news has no cache)")
    parser.parse_args()
    main()
